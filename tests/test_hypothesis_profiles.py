import json
from pathlib import Path

import pytest

from benchmarks.hypothesis_files import (
    read_hypothesis_file,
    write_hypothesis_file,
)
from benchmarks.profile_baseline import build_command
from benchmarks.profile_ga import (
    hypothesis_env,
    replay_hypothesis_metrics,
    run_profile_worker,
)
from gentians import timing
from gentians.arguments import Arguments
from gentians.rule_generation.program import Program
from gentians.rule_generation.rule_space import RuleSpace


def _arguments(tmp_path, **kwargs):
    task = tmp_path / "coin.txt"
    if not task.exists():
        task.write_text("coin(c1).\n", encoding="utf-8")
    return Arguments(filename=str(task), **kwargs)


def test_hypothesis_file_ignores_ga_only_arguments(tmp_path):
    path = tmp_path / "coin.json"
    generated = _arguments(tmp_path, iterations_genetic=1)
    requested = _arguments(tmp_path, iterations_genetic=999)

    write_hypothesis_file(path, "coin", generated, RuleSpace.from_clauses(["rule."]))

    rule_space = read_hypothesis_file(path, requested)

    assert rule_space.clauses == ("rule.",)


def test_hypothesis_file_stores_entries_to_avoid_reparse(monkeypatch, tmp_path):
    path = tmp_path / "coin.json"
    arguments = _arguments(tmp_path)
    write_hypothesis_file(path, "coin", arguments, RuleSpace.from_clauses(["rule."]))
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert "entries" in payload
    assert "clauses" not in payload

    monkeypatch.setattr(
        "benchmarks.hypothesis_files.RuleSpace.from_clauses",
        lambda clauses: (_ for _ in ()).throw(AssertionError("unexpected reparse")),
    )
    monkeypatch.setattr(
        "benchmarks.hypothesis_files.RuleSpace.from_entries",
        lambda entries: (_ for _ in ()).throw(AssertionError("unexpected rebuild")),
    )

    rule_space = read_hypothesis_file(path, arguments)

    assert rule_space.clauses == ("rule.",)


def test_hypothesis_file_rejects_changed_task_content(tmp_path):
    path = tmp_path / "coin.json"
    arguments = _arguments(tmp_path)
    write_hypothesis_file(path, "coin", arguments, RuleSpace.from_clauses(["rule."]))

    Path(arguments.filename).write_text("coin(c2).\n", encoding="utf-8")

    with pytest.raises(ValueError, match="does not match"):
        read_hypothesis_file(path, arguments)


def test_build_command_accepts_profile_script_path():
    cmd, payload = build_command("python", Arguments(), Path("benchmarks/profile_ga.py"))

    assert cmd == ["python", str(Path("benchmarks/profile_ga.py"))]
    assert json.loads(payload)["iterations_genetic"] == Arguments().iterations_genetic


def test_profile_ga_parent_validates_without_loading_rule_space(monkeypatch, tmp_path):
    path = tmp_path / "coin.json"
    arguments = _arguments(tmp_path)
    write_hypothesis_file(path, "coin", arguments, RuleSpace.from_clauses(["rule."]))
    monkeypatch.setattr(
        "benchmarks.profile_ga.read_hypothesis_payload",
        lambda path, arguments: (_ for _ in ()).throw(AssertionError("unexpected load")),
    )

    env = hypothesis_env(tmp_path)("coin", arguments)

    assert env["GENTIANS_HYPOTHESIS_SPACE_PATH"] == str(path.resolve())


def test_profile_ga_worker_loads_hypothesis_file(monkeypatch, tmp_path):
    path = tmp_path / "coin.json"
    arguments = _arguments(tmp_path)
    write_hypothesis_file(path, "coin", arguments, RuleSpace.from_clauses(["rule."]))
    captured = {}
    timing.reset()
    monkeypatch.setattr(timing, "_enabled", True)
    values = iter([1.0, 3.5])
    monkeypatch.setattr("benchmarks.profile_ga.time.perf_counter", lambda: next(values))

    monkeypatch.setenv("GENTIANS_ARGUMENTS_JSON", json.dumps(arguments.__dict__))
    monkeypatch.setenv("GENTIANS_HYPOTHESIS_SPACE_PATH", str(path))
    monkeypatch.setattr(
        "benchmarks.profile_ga.program_from_arguments",
        lambda loaded: Program([], [], [], [], []),
    )

    def fake_solve(program, loaded, rule_space, start_total_time=None):
        captured["clauses"] = rule_space.clauses
        captured["arguments"] = loaded
        captured["start_total_time"] = start_total_time

    monkeypatch.setattr("benchmarks.profile_ga.solve", fake_solve)

    run_profile_worker()

    assert captured["clauses"] == ("rule.",)
    assert captured["arguments"].filename == str(tmp_path / "coin.txt")
    assert captured["start_total_time"] is not None
    assert timing._totals["hypothesis_load"] == 2.5
    assert "hypothesis_space" not in timing._totals
    assert "hypothesis_space.self" not in timing._totals
    assert "total_execution" not in timing._totals
    timing.reset()


def test_profile_ga_replays_hypothesis_metrics(monkeypatch, tmp_path):
    timing.reset()
    clingo_path = tmp_path / "clingo.jsonl"
    events_path = tmp_path / "events.jsonl"
    monkeypatch.setenv("GENTIANS_CLINGO_METRICS_PATH", str(clingo_path))
    monkeypatch.setenv("GENTIANS_TIMING_EVENTS_PATH", str(events_path))

    replay_hypothesis_metrics(
        {
            "timings": [
                {"metric": "hypothesis_space", "seconds": 2.0, "calls": 1},
                {"metric": "hypothesis_space.self", "seconds": 0.5, "calls": 1},
                {"metric": "hypothesis_space.grounding", "seconds": 0.7, "calls": 1},
            ],
            "clingoMetrics": [
                {"operation": "hypothesis_space_grounding", "seconds": 0.7}
            ],
        }
    )

    assert timing._totals["hypothesis_space"] == 2.0
    assert timing._totals["total_execution"] == 2.0
    timing.export()
    assert "hypothesis_space_grounding" in clingo_path.read_text(encoding="utf-8")
    assert "hypothesis_space" in events_path.read_text(encoding="utf-8")
    timing.reset()
