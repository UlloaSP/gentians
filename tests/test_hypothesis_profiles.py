import json
from pathlib import Path

import pytest

from benchmarks.hypothesis_files import read_hypothesis_file, write_hypothesis_file
from benchmarks.profile_baseline import build_command
from benchmarks.profile_ga import replay_hypothesis_metrics, run_profile_worker
from gentians import timing
from gentians.arguments import Arguments
from gentians.rule_generation.program import Program
from gentians.rule_generation.rule_space import RuleSpace


def test_hypothesis_file_ignores_ga_only_arguments(tmp_path):
    path = tmp_path / "coin.json"
    generated = Arguments(filename="coin.txt", iterations_genetic=1)
    requested = Arguments(filename="coin.txt", iterations_genetic=999)

    write_hypothesis_file(path, "coin", generated, RuleSpace.from_clauses(["rule."]))

    rule_space = read_hypothesis_file(path, requested)

    assert rule_space.clauses == ["rule."]


def test_hypothesis_file_rejects_generation_argument_mismatch(tmp_path):
    path = tmp_path / "coin.json"
    write_hypothesis_file(
        path,
        "coin",
        Arguments(filename="coin.txt", max_depth=3),
        RuleSpace.from_clauses(["rule."]),
    )

    with pytest.raises(ValueError, match="does not match"):
        read_hypothesis_file(path, Arguments(filename="coin.txt", max_depth=4))


def test_build_command_accepts_profile_script_path():
    cmd, payload = build_command("python", Arguments(), Path("benchmarks/profile_ga.py"))

    assert cmd == ["python", str(Path("benchmarks/profile_ga.py"))]
    assert json.loads(payload)["iterations_genetic"] == 1000


def test_profile_ga_worker_loads_hypothesis_file(monkeypatch, tmp_path):
    path = tmp_path / "coin.json"
    arguments = Arguments(filename="coin.txt")
    write_hypothesis_file(path, "coin", arguments, RuleSpace.from_clauses(["rule."]))
    captured = {}

    monkeypatch.setenv("GENTIANS_ARGUMENTS_JSON", json.dumps(arguments.__dict__))
    monkeypatch.setenv("GENTIANS_HYPOTHESIS_SPACE_PATH", str(path))
    monkeypatch.setattr(
        "benchmarks.profile_ga.program_from_arguments",
        lambda loaded: Program([], [], [], [], []),
    )

    def fake_solve(program, loaded, rule_space):
        captured["clauses"] = rule_space.clauses
        captured["arguments"] = loaded

    monkeypatch.setattr("benchmarks.profile_ga.solve", fake_solve)

    run_profile_worker()

    assert captured["clauses"] == ["rule."]
    assert captured["arguments"].filename == "coin.txt"


def test_profile_ga_replays_hypothesis_metrics(monkeypatch, tmp_path):
    timing._totals.clear()
    timing._counts.clear()
    timing._timings_dirty = False
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
    assert "hypothesis_space_grounding" in clingo_path.read_text(encoding="utf-8")
    assert "hypothesis_space" in events_path.read_text(encoding="utf-8")
    timing._totals.clear()
    timing._counts.clear()
