"""Check a saved hypothesis with a separate ASP program for each example."""

import argparse
import gzip
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import clingo

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from gentians.language import parse_file  # noqa: E402
from gentians.language.asp import parse_program, render_program  # noqa: E402
from gentians.language.ir.example import Example  # noqa: E402
from gentians.language.ir.inductive_task import InductiveTask  # noqa: E402
from gentians.language.lexer import lex  # noqa: E402


def read_hypothesis(path: Path) -> str:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as file:
            return file.read()
    return path.read_text(encoding="utf-8")


def external_helpers(path: Path) -> str:
    """Recognize the audited arithmetic translations; never import learner task facts."""
    allowed = {str(rule) for rule in parse_program(
        "add(A,B,C) :- number(A), number(B), C = A + B.\n"
        "sub(A,B,C) :- number(A), number(B), C = A - B.\n"
        "lt(A,B) :- number(A), number(B), A < B.\n"
        "diff(A,B) :- v(A), v(B), A != B."
    )}
    source = "\n".join(
        statement.text for statement in lex(path.read_text(encoding="utf-8"))
        if (statement.directive or "").removeprefix("#") not in {"modeh", "modeb", "modec", "modeha", "modehd",
                                       "maxv", "max_penalty", "minhl", "maxhl", "maxbl",
                                       "pos", "neg", "bias", "constant"}
        and not re.match(r"^\d+\s*~", statement.text)
    )
    return "\n".join(str(rule) for rule in parse_program(source) if str(rule) in allowed)


def example_program(background: str, hypothesis: str, example: Example) -> str:
    return "\n".join((
        background, hypothesis, example.context_text,
        *(f":- not {atom}." for atom in example.included),
        *(f":- {atom}." for atom in example.excluded),
        "",
    ))


def check_hypothesis(
    task: InductiveTask, hypothesis: str, output: Path, *, helpers: str = "",
) -> dict:
    started = time.perf_counter()
    # A hypothesis must contain only executable ASP, never learner diagnostics.
    parse_program(hypothesis)
    background = "\n".join((*render_program(task.background), helpers))
    programs = output.with_name(output.stem + "_programs")
    programs.mkdir(parents=True, exist_ok=True)
    report = {"status": "running", "valid": None,
              "hypothesis_sha256": hashlib.sha256(hypothesis.encode()).hexdigest(),
              "background_sha256": hashlib.sha256(background.encode()).hexdigest(), "examples": []}
    for kind, examples in (("positive", task.positive_examples), ("negative", task.negative_examples)):
        for index, example in enumerate(examples):
            program = example_program(background, hypothesis, example)
            program_path = programs / f"{kind}_{index}.lp.gz"
            with gzip.open(program_path, "wt", encoding="utf-8") as file:
                file.write(program)
            control = clingo.Control(["--models=1", "--opt-mode=ignore"], logger=lambda *_: None)
            control.add("base", [], program)
            control.ground([("base", [])])
            witness = []
            result = control.solve(on_model=lambda model: witness.extend(
                sorted(map(str, model.symbols(atoms=True)))
            ))
            extends = bool(result.satisfiable) if not result.unknown else None
            report["examples"].append({
                "kind": kind, "index": index, "extends": extends,
                "passed": extends == (kind == "positive") if extends is not None else None,
                "program_path": str(program_path.relative_to(output.parent)), "witness": witness,
            })
            write_report(output, report)
    unknown = any(item["passed"] is None for item in report["examples"])
    report.update(status="unknown" if unknown else "complete",
                  valid=None if unknown else all(item["passed"] is True for item in report["examples"]),
                  elapsed_seconds=time.perf_counter() - started)
    write_report(output, report)
    return report


def write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def validate_run(
    task_path: Path, hypothesis_path: Path, output: Path, *, timeout_seconds: int = 60,
    learner_task_path: Path | None = None,
) -> dict:
    if not hypothesis_path.exists():
        report = {"status": "missing_hypothesis", "valid": None, "examples": []}
        write_report(output, report)
        return report
    command = [sys.executable, str(Path(__file__).resolve()), "--task", str(task_path),
               "--hypothesis", str(hypothesis_path), "--output", str(output)]
    if learner_task_path is not None:
        command.extend(("--learner-task", str(learner_task_path)))
    try:
        completed = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True,
                                   encoding="utf-8", timeout=timeout_seconds, check=False)
        if output.exists():
            report = json.loads(output.read_text(encoding="utf-8"))
        else:
            report = {"status": "error", "valid": None, "examples": []}
        if completed.returncode not in (0, 1):
            report.update(status="error", valid=None, error=completed.stderr)
    except subprocess.TimeoutExpired:
        report = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {"examples": []}
        report.update(status="timeout", valid=None)
    except OSError as error:
        report = {"status": "error", "valid": None, "examples": [], "error": str(error)}
    write_report(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--hypothesis", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--learner-task", type=Path, help="Learner task containing audited translation helpers.")
    args = parser.parse_args()
    try:
        report = check_hypothesis(parse_file(str(args.task)), read_hypothesis(args.hypothesis), args.output,
                                  helpers=external_helpers(args.learner_task) if args.learner_task else "")
        return 0 if report["valid"] else 1
    except (ValueError, RuntimeError, OSError) as error:
        write_report(args.output, {"status": "error", "valid": None, "error": str(error), "examples": []})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
