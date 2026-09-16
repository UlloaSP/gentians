from pathlib import Path
from dataclasses import replace

import pytest

from benchmarks import run_ilasp_experiments as runner

from benchmarks.run_ilasp_experiments import (
    build_command,
    fingerprint,
    load_experiments,
    summarize,
)


def write_config(tmp_path: Path) -> tuple[Path, Path]:
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    task = tasks / "tiny.las"
    task.write_text("#modeh(p).\n", encoding="utf-8")
    config = tmp_path / "experiments.toml"
    config.write_text(
        f"""
[suite]
output_root = "{(tmp_path / 'output').as_posix()}"
task_dir = "{tasks.as_posix()}"
distro = "kali-linux"
executable = "/opt/ILASP"
python_runtime = "/opt/python"
versions = ["2", "4"]
runs = 3
timeout_seconds = 20

[suite.max_body_length]
tiny = 2

[[experiment]]
id = "bias/tiny"
description = "Tiny task"
datasets = ["tiny"]
""",
        encoding="utf-8",
    )
    return config, task


def test_loads_inherited_experiment_and_builds_command(tmp_path: Path, monkeypatch) -> None:
    config, _task = write_config(tmp_path)

    experiment = load_experiments(config)[0]
    monkeypatch.setattr(runner.platform, "system", lambda: "Linux")
    command = build_command(experiment, "tiny", "4", _task)

    assert experiment.id == "bias/tiny"
    assert experiment.versions == ("2", "4")
    assert experiment.output_dir == tmp_path / "output" / "bias" / "tiny"
    assert "--version=4" in command
    assert "-ml=2" in command
    assert command[-1] == str(_task.resolve())
    assert command[:3] == ["env", "LD_LIBRARY_PATH=/opt/python/lib/x86_64-linux-gnu",
                           "PYTHONHOME=/opt/python"]


@pytest.mark.parametrize("system", ["Linux", "Windows"])
@pytest.mark.parametrize("distro", ["", "kali-linux"])
def test_relative_executable_native_and_wsl(tmp_path: Path, monkeypatch, system, distro) -> None:
    config, task = write_config(tmp_path)
    experiment = replace(load_experiments(config)[0], executable="tools/ilasp/ILASP",
                         python_runtime="", distro=distro)
    monkeypatch.setattr(runner.platform, "system", lambda: system)
    monkeypatch.setattr(runner, "windows_to_wsl", lambda path: "/mnt/c/" + path.name)

    command = build_command(experiment, "tiny", "2i", task)

    if system == "Windows":
        prefix = ["wsl", "-d", distro, "--"] if distro else ["wsl", "--"]
        assert command[:len(prefix)] == prefix
        assert command[-1] == "/mnt/c/tiny.las"
        assert command[-4] == "/mnt/c/ILASP"
    else:
        assert command[0] == "timeout"
        assert command[-1] == str(task.resolve())
        assert command[-4] == str((runner.REPO_ROOT / "tools/ilasp/ILASP").resolve())
    assert "env" not in command
    assert "--signal=INT" in command
    assert "--kill-after=5s" in command
    assert "20s" in command
    assert "--version=2i" in command


def test_optional_runtime_fields(tmp_path: Path) -> None:
    config, _ = write_config(tmp_path)
    config.write_text(config.read_text().replace('distro = "kali-linux"', '')
                      .replace('python_runtime = "/opt/python"', ''))
    experiment = load_experiments(config)[0]
    assert experiment.distro == experiment.python_runtime == ""


def test_fingerprint_changes_with_binary(tmp_path: Path) -> None:
    config, _ = write_config(tmp_path)
    executable = tmp_path / "ILASP"
    executable.write_bytes(b"first binary")
    experiment = replace(load_experiments(config)[0], executable=str(executable))
    before = fingerprint(experiment)
    executable.write_bytes(b"different binary")
    assert fingerprint(experiment) != before


def test_fingerprint_changes_with_task(tmp_path: Path) -> None:
    config, task = write_config(tmp_path)
    experiment = load_experiments(config)[0]
    before = fingerprint(experiment)

    task.write_text("#modeh(q).\n", encoding="utf-8")

    assert fingerprint(experiment) != before


def test_summary_uses_timeout_as_par1() -> None:
    rows = [
        {
            "dataset": "tiny",
            "version": "4",
            "status": "ok",
            "total_seconds": "2.0",
            "wall_seconds": "2.5",
        },
        {
            "dataset": "tiny",
            "version": "4",
            "status": "timeout",
            "total_seconds": "",
            "wall_seconds": "25.0",
        },
    ]

    result = summarize(rows, timeout_seconds=20)[0]

    assert result["solved"] == 1
    assert result["timeouts"] == 1
    assert result["mean_par1_seconds"] == "11.000000"
    assert result["mean_solved_seconds"] == "2.000000"
