import csv
import gzip
import json
import subprocess
from pathlib import Path

import pytest

from benchmarks import ilasp
from benchmarks.run_experiments import expand_experiments, load_config


def experiment(tmp_path: Path, variants=("2", "2i")) -> dict:
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    for dataset in ("coin", "grandparent"):
        (tasks / f"{dataset}.las").write_text("#modeh(p).\n", encoding="utf-8")
    return {"id": "comparison/ilasp-2", "method": "ilasp-2", "variant": variants[0],
            "datasets": ["coin", "grandparent"], "runs": 1, "timeout_seconds": 20,
            "validation_timeout_seconds": 10, "tool_options": {
                "task_dir": str(tasks), "executable": "tools/ilasp/ILASP", "distro": "kali-linux",
                "max_body_length": {"coin": 2, "grandparent": 3},
            }}


@pytest.mark.parametrize("system", ["Linux", "Windows"])
@pytest.mark.parametrize("distro", ["", "kali-linux"])
def test_build_command_native_and_wsl(tmp_path, monkeypatch, system, distro):
    configured = experiment(tmp_path)
    configured["tool_options"]["distro"] = distro
    monkeypatch.setattr(ilasp.platform, "system", lambda: system)
    monkeypatch.setattr(ilasp, "linux_path", lambda path: str(path.resolve()) if system == "Linux" else "/mnt/c/" + path.name)
    command = ilasp.build_command(configured, "coin")
    if system == "Windows":
        prefix = ["wsl", "-d", distro, "--"] if distro else ["wsl", "--"]
        assert command[:len(prefix)] == prefix
        assert command[-1] == "/mnt/c/coin.las"
    else:
        assert command[0] == "timeout"
    assert "--signal=INT" in command and "--kill-after=5s" in command
    assert "--version=2" in command and "-ml=2" in command and "20s" in command


def test_optional_python_runtime(tmp_path, monkeypatch):
    configured = experiment(tmp_path)
    configured["tool_options"]["python_runtime"] = "/opt/python"
    monkeypatch.setattr(ilasp.platform, "system", lambda: "Linux")
    assert ilasp.build_command(configured, "coin")[:3] == [
        "env", "LD_LIBRARY_PATH=/opt/python/lib/x86_64-linux-gnu", "PYTHONHOME=/opt/python",
    ]


@pytest.mark.parametrize("stdout,code,expected", [
    ("%% Total : 2.0s\np(X) :- q(X); not r(X).\n", 0, "p(X) :- q(X); not r(X).\n"),
    ("%% Total : 2.0s\n", 0, "\n"),
    ("UNSATISFIABLE\n", 0, None),
    ("", 124, None),
    ("warning: unexpected diagnostic\np.\n", 0, None),
    ("p :-\n", 124, None),
    ("%% best hypothesis\np.\n", 124, "p.\n"),
])
def test_hypothesis_extraction(stdout, code, expected):
    assert ilasp.extract_hypothesis(stdout, code) == expected


@pytest.mark.parametrize("returncode", [0, 124])
def test_runs_once_per_task_saves_hypothesis_and_resumes(tmp_path, monkeypatch, returncode):
    configured = experiment(tmp_path)
    calls = []
    monkeypatch.setattr(ilasp.platform, "system", lambda: "Linux")

    def execute(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, returncode, "%% Total : 2.0s\np.\n", "")

    def validate(task, hypothesis, output, **kwargs):
        output.write_text(json.dumps({"valid": True}), encoding="utf-8")
        assert hypothesis.read_text() == "p.\n"
        return {"valid": True}

    monkeypatch.setattr(ilasp.subprocess, "run", execute)
    monkeypatch.setattr(ilasp, "validate_run", validate)
    assert ilasp.run_experiment(configured, tmp_path / "output") == 0
    assert len(calls) == 2
    with (tmp_path / "output/runs.csv").open(newline="") as file:
        rows = list(csv.DictReader(file))
    assert [(row["dataset"], row["run"]) for row in rows] == [("coin", "1"), ("grandparent", "1")]
    assert {row["status"] for row in rows} == {"ok" if returncode == 0 else "timeout"}
    for row in rows:
        with gzip.open(tmp_path / "output" / row["hypothesis_path"], "rt") as file:
            assert file.read() == "p.\n"
        assert row["success"] == "True" and row["validation_path"].endswith(".gz")
    ilasp.run_experiment(configured, tmp_path / "output")
    assert len(calls) == 2


def test_shared_config_selects_ilasp_versions_and_fixed_run_count(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[suite]\ndatasets=["coin"]\nruns=30\n[[experiment]]\nid="paired"\n'
                      'methods=["gentians-steady_state","gentians-incremental","ilasp-2","ilasp-2i"]\n')
    _, definitions = load_config(config)
    expanded = expand_experiments(definitions)
    assert [item["runs"] for item in expanded] == [30, 30, 1, 1]
    assert [item["variant"] for item in expanded] == ["steady_state", "incremental", "2", "2i"]
