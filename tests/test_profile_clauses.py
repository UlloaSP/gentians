import json
import sys
from pathlib import Path

import pytest

from benchmarks import profile_clauses
from benchmarks.profile_clauses import main
from gentians import timing
from gentians.clauses import ClauseSpace


@pytest.mark.parametrize("cprofile", [False, True])
def test_profile_clauses_runs_standalone(monkeypatch, tmp_path, capsys, cprofile):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "profile_clauses.py",
            "--debug",
            "--datasets",
            "grandparent",
            "--out-dir",
            str(tmp_path),
            *(["--cprofile"] if cprofile else []),
        ],
    )

    main()

    payload = json.loads((tmp_path / "grandparent.json").read_text(encoding="utf-8"))
    assert payload["entries"]
    assert payload["metrics"]["timings"]
    assert payload["metrics"]["clingoMetrics"]
    output = capsys.readouterr().out
    assert f"grandparent: {len(payload['entries']):,} final clauses" in output
    assert "Final clauses / generation wall-clock:" in output
    assert "Final clauses / net generation:" in output
    assert "JSON serialization + write:" in output
    assert "Peak RSS (process so far, including JSON):" in output
    assert str(tmp_path / "grandparent.json") in output
    profile_path = tmp_path / "grandparent.python-profile.prof"
    if cprofile:
        assert profile_path.exists()
        summary = json.loads(profile_path.with_suffix(".json").read_text(encoding="utf-8"))
        models = sum(
            row["models"] for row in payload["metrics"]["clingoMetrics"]
            if row["operation_category"] == "solving"
        )
        assert summary["decodeCalls"] == models
        assert summary["clauses"] == len(payload["entries"])
        assert "Function self-time buckets" in output
        assert "clingo.Symbol access/conversion" in output
        assert "Cumulative times overlap" in output
        assert str(profile_path) in output
    else:
        assert not profile_path.exists()


def test_profile_report_uses_final_clauses_and_post_pruning_models(tmp_path, capsys):
    path = tmp_path / "clauses.json"
    path.write_text("{}", encoding="utf-8")
    metrics = {
        "timings": [
            {"metric": "clause_generation", "seconds": 2.0},
            {"metric": "clause_generation.self", "seconds": 2.0},
            {"metric": "clause_generation.grounding", "seconds": 0.5},
            {"metric": "clause_generation.solving", "seconds": 0.3},
        ],
        "clingoMetrics": [
            {"phase_context": "clause_generation", "operation_category": "grounding",
             "stats_atoms": 100, "stats_rules": 200},
            {"phase_context": "clause_generation", "operation_category": "solving",
             "models": 3000, "stats_choices": 400, "stats_conflicts": 50},
            {"phase_context": "clause_generation", "operation_category": "solving",
             "models": 2000, "stats_choices": 600, "stats_conflicts": 30},
            {"phase_context": "initialization", "operation_category": "solving",
             "models": 99999, "stats_choices": 99999, "stats_conflicts": 99999},
        ],
    }

    profile_clauses.print_profile_report(
        "example", 1000, metrics,
        loading_seconds=1.0, generation_wall_seconds=2.5,
        serialization_seconds=0.5, total_seconds=4.0,
        peak_memory_bytes=32 * 2**20, path=path,
    )

    output = capsys.readouterr().out
    for expected in (
        "example: 1,000 final clauses",
        "Task loading: 1.000s",
        "Clause generation (net): 2.000s",
        "Grounding: 0.500s (25.0%)",
        "Solving: 0.300s (15.0%)",
        "Python: 1.200s (60.0%)",
        "Generation wall-clock (including profiling/export): 2.500s",
        "JSON serialization + write: 0.500s",
        "Total wall-clock (load + generation + JSON): 4.000s",
        "Final clauses / generation wall-clock: 400.00/s",
        "Final clauses / net generation: 500.00/s",
        "Amortized net generation time: 2,000.00 us/clause",
        "Final clauses / total wall-clock: 250.00/s",
        "Enumerated models / net generation: 2,500.00/s",
        "Clingo models (after ASP pruning): 5,000",
        "Removed/merged after enumeration: 4,000",
        "Post-enumeration retention (final clauses / models): 20.00%",
        "Pre-pruning candidates, raw throughput and global survival: N/A",
        "Ground calls: 1; solve calls: 2",
        "Ground atoms: 100",
        "Ground rules: 200",
        "Choices: 1,000",
        "Conflicts: 80",
        "Peak RSS (process so far, including JSON): 32.00 MiB",
    ):
        assert expected in output


@pytest.mark.parametrize("generation,models", [(0.0, 0), (1.0, 0), (None, None)])
def test_profile_report_handles_empty_spaces_and_missing_metrics(
    generation, models, tmp_path, capsys,
):
    path = tmp_path / "empty.json"
    path.write_text("{}", encoding="utf-8")
    metrics = {
        "timings": [] if generation is None else [
            {"metric": "clause_generation", "seconds": generation},
            {"metric": "clause_generation.grounding", "seconds": 0.0},
            {"metric": "clause_generation.solving", "seconds": 0.0},
        ],
        "clingoMetrics": [] if models is None else [
            {"phase_context": "clause_generation", "operation_category": "solving",
             "models": models, "stats_choices": 0, "stats_conflicts": 0},
        ],
    }

    profile_clauses.print_profile_report(
        "empty", 0, metrics,
        loading_seconds=0.0, generation_wall_seconds=0.0,
        serialization_seconds=0.0, total_seconds=0.0,
        peak_memory_bytes=0, path=path,
    )

    output = capsys.readouterr().out
    assert "Amortized net generation time: N/A" in output
    assert "Final clauses / total wall-clock: N/A" in output
    assert "Post-enumeration retention (final clauses / models): N/A" in output
    assert "inf" not in output
    assert "nan" not in output


@pytest.mark.parametrize("enabled", [False, True])
def test_profile_clauses_restores_instrumentation_after_failure(monkeypatch, enabled):
    previous_enabled = timing.is_enabled()
    monkeypatch.setenv("GENTIANS_TIMINGS_PATH", "original-timings.json")
    monkeypatch.delenv("GENTIANS_CLINGO_METRICS_PATH", raising=False)

    def fail(task, arguments):
        assert timing.is_enabled()
        raise RuntimeError("generation failed")

    monkeypatch.setattr(profile_clauses, "generate_clause_space", fail)
    try:
        timing.set_enabled(enabled)
        with pytest.raises(RuntimeError, match="generation failed"):
            profile_clauses.build_profiled_clause_space(None, None)
        assert timing.is_enabled() is enabled
        assert profile_clauses.os.environ["GENTIANS_TIMINGS_PATH"] == "original-timings.json"
        assert "GENTIANS_CLINGO_METRICS_PATH" not in profile_clauses.os.environ
    finally:
        timing.set_enabled(previous_enabled)


def test_profile_clauses_loads_all_alzheimer_tasks(monkeypatch, tmp_path):
    seen = []

    def capture(task, arguments):
        seen.append((arguments.filename, len(task.positive_examples)))
        return ClauseSpace(()), {"timings": [], "clingoMetrics": []}

    monkeypatch.setattr(profile_clauses, "build_profiled_clause_space", capture)
    monkeypatch.setattr(
        sys, "argv",
        ["profile_clauses.py", "--debug", "--datasets", "alzheimer", "--out-dir", str(tmp_path)],
    )

    main()

    assert [(Path(filename).name, count) for filename, count in seen] == [
        ("alzheimer_acetyl", 530),
        ("alzheimer_amine", 274),
        ("alzheimer_mem", 256),
        ("alzheimer_toxic", 354),
    ]
    assert {path.stem for path in tmp_path.glob("*.json")} == {
        "alzheimer_acetyl", "alzheimer_amine", "alzheimer_mem", "alzheimer_toxic"
    }


def test_default_output_is_only_a_table_and_creates_no_files(monkeypatch, tmp_path, capsys):
    out_dir = tmp_path / "unused"

    def no_profiling(*args):
        pytest.fail("compact mode must not run profiling or write metric files")

    monkeypatch.setattr(profile_clauses, "build_profiled_clause_space", no_profiling)
    monkeypatch.setattr(sys, "argv", ["profile_clauses.py", "--datasets", "grandparent", "subset_sum",
                                     "--out-dir", str(out_dir)])
    main()

    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split() == ["Benchmark", "Clauses", "Time", "(s)"]
    assert len(lines) == 4
    assert lines[2].split()[:2] == ["grandparent", "326"]
    assert lines[3].split()[:2] == ["subset_sum", "8"]
    assert all(float(line.split()[-1]) >= 0 for line in lines[2:])
    assert not out_dir.exists()
    assert not list(tmp_path.iterdir())


def test_compact_time_excludes_task_loading(monkeypatch, capsys):
    clock = [0.0]
    monkeypatch.setattr(profile_clauses.time, "perf_counter", lambda: clock[0])

    def load(arguments):
        clock[0] += 12.0
        return None

    def generate(task, arguments):
        clock[0] += 2.5
        return ClauseSpace(())

    monkeypatch.setattr(profile_clauses, "task_from_arguments", load)
    monkeypatch.setattr(profile_clauses, "generate_clause_space", generate)
    monkeypatch.setattr(sys, "argv", ["profile_clauses.py", "--datasets", "grandparent"])
    main()
    assert capsys.readouterr().out.splitlines()[-1].split() == ["grandparent", "0", "2.500"]


def test_cprofile_requires_debug_before_any_generation(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(sys, "argv", ["profile_clauses.py", "--cprofile", "--datasets", "grandparent",
                                     "--out-dir", str(tmp_path)])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert "--cprofile requires --debug" in capsys.readouterr().err
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("fail", [False, True])
def test_compact_mode_disables_and_restores_ambient_instrumentation(monkeypatch, tmp_path, fail):
    previous_enabled = timing.is_enabled()
    path = str(tmp_path / "clingo.jsonl")
    monkeypatch.setenv("GENTIANS_CLINGO_METRICS_PATH", path)
    monkeypatch.setattr(sys, "argv", ["profile_clauses.py", "--datasets", "grandparent",
                                     "--out-dir", str(tmp_path / "unused")])

    def generate(task, arguments):
        assert not timing.is_enabled()
        assert not timing.metric_enabled("clingo")
        if fail:
            raise RuntimeError("generation failed")
        return ClauseSpace(())

    monkeypatch.setattr(profile_clauses, "generate_clause_space", generate)
    try:
        timing.set_enabled(True)
        if fail:
            with pytest.raises(RuntimeError, match="generation failed"):
                main()
        else:
            main()
        assert timing.is_enabled()
        assert profile_clauses.os.environ["GENTIANS_CLINGO_METRICS_PATH"] == path
        assert not list(tmp_path.iterdir())
    finally:
        timing.set_enabled(previous_enabled)
