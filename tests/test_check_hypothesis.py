import gzip
import json
import subprocess

import pytest

from benchmarks import check_hypothesis as checker
from gentians.language.parser import parse_text


@pytest.mark.parametrize("hypothesis,valid", [("p :- not q.", True), ("p :- not q.\nq.", False), ("", False)])
def test_checks_whole_program_with_default_negation(tmp_path, hypothesis, valid):
    task = parse_text("#pos({p},{}). #neg({q},{}).")
    report = checker.check_hypothesis(task, hypothesis, tmp_path / "validation.json")
    assert report["valid"] is valid
    assert len(report["examples"]) == 2
    for example in report["examples"]:
        with gzip.open(tmp_path / example["program_path"], "rt") as file:
            assert hypothesis in file.read()


@pytest.mark.parametrize("examples,program,valid", [
    ("#pos({p},{q}).", "p.", True),
    ("#pos({p},{q}).", "p. q.", False),
    ("#pos({},{q}).", "p.", True),
    ("#pos({p},{}).", "q.", False),
    ("#neg({p},{q}).", "p. q.", True),
    ("#neg({p},{q}).", "p.", False),
    ("#pos({-p},{p}).", "-p.", True),
    ("#pos({},{}).", "", True),
    ("#pos({},{}).", ":-.", False),
    ("#neg({},{}).", ":-.", True),
])
def test_included_excluded_empty_sides_and_strong_negation(tmp_path, examples, program, valid):
    assert checker.check_hypothesis(parse_text(examples), program, tmp_path / "check.json")["valid"] is valid


def test_each_positive_can_have_its_own_stable_model(tmp_path):
    task = parse_text("1 {p;q} 1. #pos({p},{q}). #pos({q},{p}).")
    report = checker.check_hypothesis(task, "", tmp_path / "check.json")
    assert report["valid"] is True


def test_contexts_do_not_leak_between_examples(tmp_path):
    task = parse_text("#pos({q},{},{p.}). #neg({q},{},{}).")
    report = checker.check_hypothesis(task, "q :- p.", tmp_path / "check.json")
    assert report["valid"] is True
    assert [item["extends"] for item in report["examples"]] == [True, False]


def test_external_helpers_keep_only_audited_translations(tmp_path):
    path = tmp_path / "task.las"
    path.write_text('#const n=2. q(1..n). helper(X):-q(X).\n'
                    'add(A,B,C) :- number(A), number(B), C=A+B.\n'
                    '#modeh(p). #modeb(q). #maxv(2). #minhl(1). #modeha(p).\n'
                    '#pos({p},{}). 2 ~ p:-q(1).\n')
    source = checker.external_helpers(path)
    assert "add(A,B,C)" in source
    assert "helper" not in source and "#const" not in source and "q(1" not in source
    assert "#mode" not in source and "2 ~" not in source and "#pos" not in source


def test_learner_background_cannot_make_original_examples_pass(tmp_path):
    learner = tmp_path / "task.las"
    learner.write_text("p. #modeh(p). #pos({p},{}).")
    task = parse_text("#pos({p},{}).")
    assert checker.check_hypothesis(task, "", tmp_path / "check.json",
                                    helpers=checker.external_helpers(learner))["valid"] is False


def test_translation_helpers_use_original_background(tmp_path):
    learner = tmp_path / "task.las"
    learner.write_text("number(1..9). add(A,B,C) :- number(A), number(B), C=A+B.")
    task = parse_text("number(1..2). #pos({p},{}). #neg({q},{}).")
    report = checker.check_hypothesis(task, "p :- add(1,2,3). q :- add(5,5,10).",
                                      tmp_path / "check.json", helpers=checker.external_helpers(learner))
    assert report["valid"] is True


def test_missing_hypothesis_is_not_an_empty_solution(tmp_path):
    report = checker.validate_run(tmp_path / "task", tmp_path / "missing.lp", tmp_path / "check.json")
    assert report["status"] == "missing_hypothesis" and report["valid"] is None


def test_validation_timeout_preserves_completed_examples(tmp_path, monkeypatch):
    hypothesis = tmp_path / "h.lp"
    hypothesis.write_text("p.")
    output = tmp_path / "check.json"

    def timeout(*args, **kwargs):
        output.write_text(json.dumps({"status": "running", "examples": [{"passed": True}]}))
        raise subprocess.TimeoutExpired(args[0], 1)

    monkeypatch.setattr(checker.subprocess, "run", timeout)
    report = checker.validate_run(tmp_path / "task", hypothesis, output, timeout_seconds=1)
    assert report["status"] == "timeout" and report["valid"] is None
    assert report["examples"] == [{"passed": True}]


def test_report_replace_retries_while_windows_locks_the_target(tmp_path, monkeypatch):
    output = tmp_path / "check.json"
    replace = type(output).replace
    failures = iter((True, True))

    def locked_replace(self, target):
        if next(failures, False):
            raise PermissionError("[WinError 5] Access is denied")
        return replace(self, target)

    monkeypatch.setattr(type(output), "replace", locked_replace)
    monkeypatch.setattr(checker.time, "sleep", lambda seconds: None)
    checker.write_report(output, {"status": "complete"})
    assert json.loads(output.read_text())["status"] == "complete"
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("returncode,written,stderr,expected_error", [
    (2, {"status": "error", "error": "PermissionError: denied", "examples": []}, "", "PermissionError: denied"),
    (1, {"status": "running", "examples": [{"passed": True}]}, "Traceback: boom", "Traceback: boom"),
    (3221225477, None, "", None),
])
def test_failed_checker_keeps_its_message_and_exit_code(
    tmp_path, monkeypatch, returncode, written, stderr, expected_error,
):
    hypothesis = tmp_path / "h.lp"
    hypothesis.write_text("p.")
    output = tmp_path / "check.json"

    def run(command, **kwargs):
        if written is not None:
            output.write_text(json.dumps(written))
        return subprocess.CompletedProcess(command, returncode, "", stderr)

    monkeypatch.setattr(checker.subprocess, "run", run)
    report = checker.validate_run(tmp_path / "task", hypothesis, output)
    assert report["status"] == "error" and report["valid"] is None
    assert report["returncode"] == returncode
    assert report.get("error") == expected_error
    assert json.loads(output.read_text()) == report


def test_invalid_hypothesis_exit_code_is_not_an_error(tmp_path, monkeypatch):
    hypothesis = tmp_path / "h.lp"
    hypothesis.write_text("p.")
    output = tmp_path / "check.json"

    def run(command, **kwargs):
        output.write_text(json.dumps({"status": "complete", "valid": False, "examples": []}))
        return subprocess.CompletedProcess(command, 1, "", "")

    monkeypatch.setattr(checker.subprocess, "run", run)
    report = checker.validate_run(tmp_path / "task", hypothesis, output)
    assert report["status"] == "complete" and report["valid"] is False and "returncode" not in report
