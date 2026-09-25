import json
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from benchmarks import profile_baseline as profile

from benchmarks.profile_baseline import (
    GAMetric,
    RunResult,
    TimingMetric,
    clingo_summary,
    dashboard_fitness_mean,
    dashboard_phases,
    dashboard_quality,
    operator_summary,
    parse_log,
    build_dashboard,
    compress_run_artifacts,
    reset_run_outputs,
    run_profile_worker,
    run_streamed,
    thin_progress,
    write_csv,
    write_dashboard_data,
    write_debug_clingo_program,
)
from gentians import timing
from gentians.algorithms import SearchResult
from gentians.arguments import Arguments
from gentians.gentians import solve
from tests.task_helpers import inductive_task


@pytest.mark.parametrize("stop,expected", [(True, 1), (False, 6)])
def test_suite_stops_configuration_after_timeout_and_keeps_results(tmp_path, monkeypatch, stop, expected):
    calls = []

    def timeout(*args, **_kwargs):
        calls.append(args)
        args[2].write_text("", encoding="utf-8")
        return -1, True

    monkeypatch.setattr(profile, "run_streamed", timeout)
    args = SimpleNamespace(list_datasets=False, out_dir=tmp_path,
                           datasets=["5queens", "grandparent"], runs=3,
                           arguments_json=None, set=[], python=sys.executable,
                           cprofile=False, seed_base=1, timeout_seconds=1,
                           instrumentation="light", stop_on_timeout=stop)
    profile.run_benchmark_suite(args, profile.PROFILE_BASELINE_PATH)
    assert len(calls) == expected
    assert (tmp_path / "runs.csv").is_file()
    assert (tmp_path / "runs.csv").read_text().count("timeout") == expected
    from benchmarks.run_experiments import result_status
    assert result_status(tmp_path, stop_on_timeout=stop) == (
        "screened_out" if stop else "completed_with_failures")


def test_profile_worker_applies_seed_to_arguments(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setenv("GENTIANS_ARGUMENTS_JSON", json.dumps(Arguments().__dict__))
    monkeypatch.setenv("GENTIANS_RANDOM_SEED", "17")
    monkeypatch.setenv("GENTIANS_TIMINGS_PATH", str(tmp_path / "run_timings.json"))
    monkeypatch.setattr(
        "benchmarks.profile_baseline.gentians_main",
        lambda arguments: captured.setdefault("arguments", arguments),
    )

    run_profile_worker()

    assert captured["arguments"].random_seed == 17


def test_parse_log_marks_only_found_best_as_success(tmp_path):
    log = tmp_path / "run.log"
    log.write_text(
        "--- Found best program with score 1.0 ---\n"
        "rule.\n"
        "--------------------------\n"
        "Total time: 0.1\n",
        encoding="utf-8",
    )

    parsed = parse_log(log)

    assert parsed["success"] is True
    assert parsed["best_program"] == ["rule."]


def test_parse_log_keeps_best_candidate_as_not_success(tmp_path):
    log = tmp_path / "run.log"
    log.write_text(
        "--- Best candidate program with score 1.0 ---\n"
        "rule.\n"
        "--------------------------\n"
        "Total time: 0.1\n",
        encoding="utf-8",
    )

    parsed = parse_log(log)

    assert parsed["success"] is False
    assert parsed["best_program"] == ["rule."]


def test_profile_baseline_writes_debug_clingo_program(tmp_path):
    task = tmp_path / "task.txt"
    task.write_text(
        "base.\n"
        "#pos({target},{}).\n"
        "#modeh(1,target).\n",
        encoding="utf-8",
    )
    arguments = Arguments(filename=str(task))

    write_debug_clingo_program(
        tmp_path / ".debug" / "clingo",
        "coin/run",
        arguments,
        ["target."],
    )

    dump = (tmp_path / ".debug" / "clingo" / "coin_run.lp").read_text(
        encoding="utf-8"
    )
    args = (tmp_path / ".debug" / "clingo" / "coin_run.args.txt").read_text(
        encoding="utf-8"
    )
    assert "base." in dump
    assert "pos_exs((0..0))." in dump
    assert "target." in dump
    assert "python -m clingo 0 " in args
    assert "--enum-mode=brave" not in args


def test_operator_summary_counts_non_finite_mutation_as_invalid():
    rows = [
        {
            "dataset": "coin",
            "operator": "mutation",
            "strategy": "x",
            "new_score": "nan",
            "original_score": "1",
            "slots": 1,
            "invalid": True,
        }
    ]

    [summary] = operator_summary(rows)

    assert summary["invalid_rate"] == 1.0


def test_operator_summary_accepts_engine_generic_schema():
    rows = [
        {
            "dataset": "coin",
            "run": 1,
            "operator": "mutation",
            "strategy": "random_group",
            "slots": 1,
            "applied": True,
            "valid_new": True,
            "changed": True,
            "original_score": 1.0,
            "new_score": 2.0,
            "improved": True,
            "is_best": False,
        }
    ]

    [summary] = operator_summary(rows)

    assert summary["valid_rate"] == 1.0
    assert summary["improvement_rate"] == 1.0
    assert summary["mean_score_delta"] == 1.0


def test_operator_summary_separates_skipped_mutations_from_duplicates():
    rows = [
        {
            "dataset": "d",
            "operator": "mutation",
            "strategy": "random_group",
            "slots": 1,
            "skipped": True,
            "duplicate": False,
        },
        {
            "dataset": "d",
            "operator": "mutation",
            "strategy": "random_group",
            "slots": 1,
            "skipped": False,
            "duplicate": True,
        },
    ]

    [summary] = operator_summary(rows)

    assert summary["skipped_rate"] == 0.5
    assert summary["duplicate_rate"] == 0.5


def test_operator_summary_marks_unobserved_score_outcomes():
    [summary] = operator_summary(
        [
            {
                "dataset": "d",
                "operator": "mutation",
                "strategy": "random_group",
                "slots": 1,
                "applied": True,
                "valid_new": True,
            }
        ]
    )

    assert summary["improvement_rate"] is None
    assert summary["worse_or_equal_rate"] is None
    assert summary["mean_score_delta"] is None


def test_operator_improvement_counts_only_scored_new_results():
    rows = [
        {"dataset": "d", "run": 1, "operator": "crossover", "strategy": "set_mix",
         "slots": 1, "valid_new": valid, "improved": improved,
         "original_score": 1.0, "new_score": new_score}
        for valid, improved, new_score in (
            (True, True, 2.0),
            (True, False, 0.5),
            (False, True, 3.0),  # A duplicate is not a new result.
            (True, False, ""),  # An unscored child has no outcome.
        )
    ]

    [summary] = operator_summary(rows)

    assert summary["improvement_rate"] == 0.5
    assert summary["worse_or_equal_rate"] == 0.5
    assert summary["mean_score_delta"] == pytest.approx(0.25)


def test_operator_summary_uses_run_means():
    [summary] = operator_summary(
        [
            {
                "dataset": "d",
                "run": 1,
                "operator": "mutation",
                "strategy": "random_group",
                "slots": 1,
                "applied": True,
                "skipped": False,
                "duplicate": False,
                "invalid": False,
                "is_best": False,
                "changed": True,
                "valid_new": True,
                "improved": True,
                "new_score": 3,
                "original_score": 1,
            },
            {
                "dataset": "d",
                "run": 2,
                "operator": "mutation",
                "strategy": "random_group",
                "slots": 1,
                "applied": False,
                "skipped": True,
                "duplicate": False,
                "invalid": False,
                "is_best": False,
                "changed": False,
                "valid_new": False,
                "improved": False,
            },
            {
                "dataset": "d",
                "run": 2,
                "operator": "mutation",
                "strategy": "random_group",
                "slots": 1,
                "applied": False,
                "skipped": True,
                "duplicate": False,
                "invalid": False,
                "is_best": False,
                "changed": False,
                "valid_new": False,
                "improved": False,
            },
        ]
    )

    assert summary["events"] == 1.5
    assert summary["changed_rate"] == 0.5
    assert summary["valid_rate"] == 0.5
    assert summary["improvement_rate"] == 1.0
    assert summary["mean_score_delta"] == 2.0


def test_dashboard_quality_preaggregates_without_changing_metrics():
    quality = dashboard_quality(
        [
            {
                "run": 1,
                "score": 1,
                "covered_positive": 0,
                "covered_negative": 1,
                "total_positive": 1,
                "total_negative": 2,
                "program_size": 2,
                "complete": False,
                "consistent": False,
            },
            {
                "run": 1,
                "score": 10,
                "covered_positive": 1,
                "covered_negative": 0,
                "total_positive": 1,
                "total_negative": 2,
                "program_size": 3,
                "best_found": True,
                "complete": True,
                "consistent": True,
            },
            {
                "run": 2,
                "score": 10,
                "covered_positive": 1,
                "covered_negative": 0,
                "total_positive": 1,
                "total_negative": 2,
                "program_size": 3,
                "best_found": True,
                "complete": True,
                "consistent": True,
            },
        ]
    )

    assert quality["extent"] == {"positive": 1, "negative": 2}
    assert [
        (point["count"], point["meanCount"], point["runs"])
        for point in quality["coveragePoints"]
    ] == [(1, 0.5, 2), (2, 1, 2)]
    assert quality["criteria"] == [
        {"key": "complete", "rate": 75, "meanCount": 1, "count": 2, "runs": 2},
        {
            "key": "incomplete",
            "rate": 25,
            "meanCount": 0.5,
            "count": 1,
            "runs": 2,
        },
        {
            "key": "consistent",
            "rate": 75,
            "meanCount": 1,
            "count": 2,
            "runs": 2,
        },
        {
            "key": "inconsistent",
            "rate": 25,
            "meanCount": 0.5,
            "count": 1,
            "runs": 2,
        },
        {"key": "both", "rate": 75, "meanCount": 1, "count": 2, "runs": 2},
    ]
    assert quality["programSizes"] == [
        {"size": 2, "evaluated": 1, "best": 0},
        {"size": 3, "evaluated": 2, "best": 2},
    ]


def test_dashboard_quality_has_no_criteria_without_measured_runs():
    quality = dashboard_quality([])

    assert quality["coveragePoints"] == []
    assert quality["criteria"] == []
    assert quality["programSizes"] == []


def test_dashboard_quality_uses_evaluation_status_flags():
    quality = dashboard_quality(
        [
            {
                "run": 1,
                "covered_positive": 1,
                "covered_negative": 0,
                "total_positive": 1,
                "total_negative": 1,
                "complete": False,
                "consistent": False,
            }
        ]
    )

    rates = {criterion["key"]: criterion["rate"] for criterion in quality["criteria"]}
    assert rates == {
        "complete": 0,
        "incomplete": 100,
        "consistent": 0,
        "inconsistent": 100,
        "both": 0,
    }


def test_solve_exports_total_execution_after_phase_closes(monkeypatch):
    timing.reset()
    monkeypatch.setattr(timing, "_enabled", True)
    exported = {}

    monkeypatch.setattr(
        "gentians.gentians.steady_state_genetic_search",
        lambda *args, **kwargs: SearchResult(("rule.",), 1.0, True),
    )

    def export():
        exported.update(timing._totals)

    monkeypatch.setattr("gentians.gentians.export_timings", export)

    solve(
        inductive_task([], [], [], [], []),
        Arguments(population={"name": "random", "size": 1}),
    )

    assert "total_execution" in exported
    assert timing._stack == []
    timing.reset()


def test_total_execution_excludes_result_output(monkeypatch):
    timing.reset()
    monkeypatch.setattr(timing, "_enabled", True)
    monkeypatch.setattr(
        "gentians.gentians.steady_state_genetic_search",
        lambda *args, **kwargs: SearchResult(("rule.",), 1.0, True),
    )
    monkeypatch.setattr("gentians.gentians.export_timings", lambda: None)
    monkeypatch.setattr("builtins.print", lambda *args, **kwargs: time.sleep(0.02))

    solve(
        inductive_task([], [], [], [], []),
        Arguments(population={"name": "random", "size": 1}),
    )

    assert timing._totals["total_execution"] < 0.02
    timing.reset()


def test_fallback_total_excludes_result_output(monkeypatch):
    timing.reset()
    monkeypatch.setattr(timing, "_enabled", False)
    clock = [10.0]
    output = []

    def search(*_args, **_kwargs):
        clock[0] += 5.0
        return SearchResult(("rule.",), 1.0, True)

    def print_result(*args, **_kwargs):
        output.append(args)
        clock[0] += 20.0

    monkeypatch.setattr("gentians.gentians.steady_state_genetic_search", search)
    monkeypatch.setattr("gentians.gentians.export_timings", lambda: None)
    monkeypatch.setattr("gentians.gentians.time.time", lambda: clock[0])
    monkeypatch.setattr("builtins.print", print_result)

    solve(
        inductive_task([], [], [], [], []),
        Arguments(population={"name": "random", "size": 1}),
        start_total_time=10.0,
    )

    assert output[-1] == ("Total time: 5.0",)


def test_net_time_excludes_instrumentation(monkeypatch):
    timing.reset()
    monkeypatch.setattr(timing, "_enabled", True)
    timing._stack.append(
        {"instrumenting": False, "instrumentation_seconds": 0.0}
    )
    values = iter([10.0, 11.0, 16.0, 20.0])
    monkeypatch.setattr(timing.time, "perf_counter", lambda: next(values))

    started = timing.net_time()
    with timing.instrumentation():
        pass

    assert timing.net_time() - started == 5.0
    timing.reset()


def test_phase_records_exclusive_self_time(monkeypatch):
    timing.reset()
    monkeypatch.setattr(timing, "_enabled", True)

    with timing.phase("outer"):
        with timing.phase("inner"):
            pass

    assert "outer.self" in timing._totals
    assert "inner.self" in timing._totals
    assert timing._totals["outer.self"] <= timing._totals["outer"]
    timing.reset()


def test_phase_subtracts_instrumentation_time(monkeypatch):
    timing.reset()
    monkeypatch.setattr(timing, "_enabled", True)
    values = iter([0.0, 0.0, 2.0, 5.0, 10.0, 10.0])
    monkeypatch.setattr(timing.time, "perf_counter", lambda: next(values))

    with timing.phase("outer"):
        with timing.instrumentation():
            pass

    assert timing._totals["outer"] == 3.0
    assert timing._totals["outer.self"] == 3.0
    timing.reset()


def test_ga_metrics_have_one_generation_coordinate(monkeypatch):
    timing.reset()
    monkeypatch.setenv("GENTIANS_GA_METRICS_PATH", "metrics.json")

    timing.record_ga_generation(
        0,
        1.0,
        [SimpleNamespace(score=1.0, genome=1)],
    )

    assert timing._ga_rows[0]["generation"] == 0
    assert "epoch" not in timing._ga_rows[0]
    assert "global_generation" not in timing._ga_rows[0]
    timing.reset()


def test_dashboard_attributes_genetic_self_to_ga_python():
    phases = dashboard_phases(
        [
            TimingMetric("d", 1, "total_execution", 10.0, 1),
            TimingMetric("d", 1, "search.self", 3.0, 1),
            TimingMetric("d", 1, "selection", 2.0, 1),
            TimingMetric("d", 1, "selection.self", 2.0, 1),
            TimingMetric("d", 1, "replacement", 5.0, 1),
            TimingMetric("d", 1, "replacement.self", 5.0, 1),
        ]
    )

    assert phases["gaPython"]["python"] == 3.0
    assert phases["replacement"]["python"] == 5.0
    assert "other" not in phases["replacement"]


def test_dashboard_phases_are_the_phases_the_algorithms_record():
    assert list(dashboard_phases([])) == [
        "clauseGeneration",
        "initialization",
        "selection",
        "crossover",
        "mutation",
        "replacement",
        "gaPython",
    ]


def test_dashboard_attributes_fitness_cost_to_operator_phase():
    phases = dashboard_phases(
        [
            TimingMetric("d", 1, "total_execution", 20.0, 1),
            TimingMetric("d", 1, "clause_generation.self", 5.0, 1),
            TimingMetric("d", 1, "clause_generation.grounding", 1.0, 1),
            TimingMetric("d", 1, "clause_generation.solving", 2.0, 1),
            TimingMetric("d", 1, "initialization.self", 10.0, 2),
            TimingMetric("d", 1, "initialization.grounding", 3.0, 2),
            TimingMetric("d", 1, "initialization.solving", 4.0, 2),
            TimingMetric("d", 1, "initialization.closure", 1.0, 2),
            TimingMetric("d", 1, "search.self", 5.0, 1),
        ]
    )

    assert phases["clauseGeneration"] == {
        "python": 2.0,
        "grounding": 1.0,
        "solving": 2.0,
        "closure": 0.0,
    }
    assert phases["initialization"] == {
        "python": 2.0,
        "grounding": 3.0,
        "solving": 4.0,
        "closure": 1.0,
    }
    assert phases["gaPython"]["python"] == 5.0


def test_dashboard_phases_use_run_means():
    phases = dashboard_phases(
        [
            TimingMetric("d", 1, "total_execution", 10.0, 1),
            TimingMetric("d", 1, "search.self", 2.0, 1),
            TimingMetric("d", 2, "total_execution", 30.0, 1),
            TimingMetric("d", 2, "search.self", 6.0, 1),
        ]
    )

    assert phases["gaPython"]["python"] == 20.0


def test_frontend_phase_order_matches_dashboard_phases():
    metrics_js = Path(".benchmarks/src/metrics.js").read_text(encoding="utf-8")
    match = re.search(
        r"phaseOrder\s*=\s*\[(.*?)\]\s*;?\s*\n\s*export const typeOrder",
        metrics_js,
        re.S,
    )
    assert match is not None
    frontend_phases = re.findall(r"\[['\"]([^'\"]+)['\"]", match.group(1))

    backend_phases = dashboard_phases([]).keys()

    assert set(frontend_phases) == set(backend_phases)


def test_clingo_summary_uses_run_means():
    [summary] = clingo_summary(
        [
            {
                "dataset": "d",
                "run": 1,
                "operation": "solving",
                "operation_category": "solving",
                "phase_context": "mutation",
                "seconds": 0.2,
                "models": 2,
                "stats_atoms": 10,
                "stats_rules": 20,
            },
            {
                "dataset": "d",
                "run": 2,
                "operation": "solving",
                "operation_category": "solving",
                "phase_context": "mutation",
                "seconds": 0.4,
                "models": 4,
                "stats_atoms": 30,
                "stats_rules": 60,
            },
            {
                "dataset": "d",
                "run": 2,
                "operation": "solving",
                "operation_category": "solving",
                "phase_context": "mutation",
                "seconds": 0.6,
                "models": 6,
                "stats_atoms": 50,
                "stats_rules": 100,
            }
        ]
    )

    assert summary["operation_category"] == "solving"
    assert summary["calls"] == 1.5
    assert summary["total_seconds"] == 0.6
    assert summary["total_models"] == 6


def test_dashboard_aggregates_clingo_by_category_and_mean_ground_size(tmp_path):
    write_dashboard_data(
        tmp_path,
        [
            RunResult(
                "d",
                1,
                1,
                "run",
                "ok",
                0,
                1.0,
                [],
                "{}",
                "",
            ),
            RunResult(
                "d",
                2,
                2,
                "run2",
                "ok",
                0,
                1.0,
                [],
                "{}",
                "",
            ),
        ],
        [],
        [],
        [],
        [],
        [],
        [
            {
                "dataset": "d",
                "run": 1,
                "operation": "grounding",
                "operation_category": "grounding",
                "phase_context": "initialization",
                "seconds": 0.5,
                "stats_atoms": 10,
                "stats_rules": 20,
            },
            {
                "dataset": "d",
                "run": 2,
                "operation": "grounding",
                "operation_category": "grounding",
                "phase_context": "initialization",
                "seconds": 0.7,
                "stats_atoms": 30,
                "stats_rules": 60,
            },
            {
                "dataset": "d",
                "run": 2,
                "operation": "solving",
                "operation_category": "solving",
                "phase_context": "mutation",
                "seconds": 0.2,
                "models": 9,
                "stats_atoms": 30,
                "stats_rules": 60,
            },
            {
                "dataset": "d",
                "run": 1,
                "operation": "solving",
                "operation_category": "solving",
                "phase_context": "mutation",
                "seconds": 0.1,
                "models": 3,
                "stats_atoms": 10,
                "stats_rules": 20,
            },
        ],
    )

    bench = json.loads((tmp_path / "dashboard_data.json").read_text())["benchmarks"][0]
    assert bench["groundCalls"] == 1
    assert bench["solveCalls"] == 1
    assert bench["atoms"] == 20
    assert bench["groundRules"] == 40
    assert bench["models"] == 6


def test_dashboard_counts_best_found_runs(tmp_path):
    write_dashboard_data(
        tmp_path,
        [
            RunResult("d", 1, 1, "run", "ok", 0, 1.0, [], "{}", ""),
            RunResult("d", 2, 2, "run", "ok", 0, 1.0, [], "{}", "", success=True),
        ],
        [],
        [],
        [],
        [],
        [],
        [],
    )

    bench = json.loads((tmp_path / "dashboard_data.json").read_text())["benchmarks"][0]
    assert bench["runCount"] == 2
    assert bench["bestFoundRuns"] == 1


def test_reset_run_outputs_removes_stale_profile_files(tmp_path):
    paths = [tmp_path / "a.jsonl", tmp_path / "b.json"]
    for path in paths:
        path.write_text("stale", encoding="utf-8")
    (tmp_path / "c.jsonl.gz").write_text("stale", encoding="utf-8")

    reset_run_outputs([*paths, tmp_path / "c.jsonl"])

    assert list(tmp_path.iterdir()) == []


def test_finished_run_keeps_only_compressed_artifacts_that_still_read(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    source = runs / "d_run_1_operator_metrics.jsonl"
    source.write_text('{"operator": "mutation"}\n', encoding="utf-8")
    timings = runs / "d_run_1_timings.json"
    timings.write_text('[{"metric": "total_execution", "seconds": 2, "calls": 1}]', encoding="utf-8")
    (runs / "d_run_1.log").write_text("log", encoding="utf-8")
    profile_file = runs / "d_run_1.prof"
    profile_file.write_bytes(b"prof")

    compress_run_artifacts(tmp_path, "d", 1)

    assert sorted(path.name for path in runs.iterdir()) == [
        "d_run_1.log.gz", "d_run_1.prof",
        "d_run_1_operator_metrics.jsonl.gz", "d_run_1_timings.json.gz",
    ]
    assert profile.read_jsonl_rows(source, "d", 1, 7, "d_seed_7") == [
        {"dataset": "d", "run": 1, "seed": 7, "experiment_id": "d_seed_7", "operator": "mutation"}
    ]
    assert profile.read_timings(timings, "d", 1) == [TimingMetric("d", 1, "total_execution", 2.0, 1)]


@pytest.mark.parametrize("timeout", [0, 10])
def test_run_streamed_sets_dataset_and_run_env(tmp_path, timeout):
    log_path = tmp_path / "run.log"
    code = (
        "import os; "
        "print(os.environ['GENTIANS_BENCHMARK_NAME']); "
        "print(os.environ['GENTIANS_RUN_NUMBER'])"
    )

    returncode, timed_out = run_streamed(
        [sys.executable, "-c", code],
        "{}",
        log_path,
        timeout,
        tmp_path / "timings.json",
        tmp_path / "ga.json",
        tmp_path / "operator.jsonl",
        tmp_path / "candidate.jsonl",
        tmp_path / "quality.jsonl",
        tmp_path / "clingo.jsonl",
        "coin",
        3,
        99,
    )

    assert (returncode, timed_out) == (0, False)
    assert log_path.read_text(encoding="utf-8").splitlines() == ["coin", "3"]


def test_light_instrumentation_removes_inherited_detailed_logging(tmp_path, monkeypatch):
    monkeypatch.setenv("GENTIANS_CLINGO_METRICS_PATH", "inherited.jsonl")
    code = "import os,json; print(json.dumps(sorted(k for k in os.environ if k.startswith('GENTIANS_') and k.endswith('_PATH'))))"
    log = tmp_path / "run.log"
    result = run_streamed(
        [sys.executable, "-c", code], "{}", log, 10,
        *[tmp_path / name for name in ("timings.json", "x_ga_metrics.json", "operator.jsonl",
                                      "candidate.jsonl", "quality.jsonl", "clingo.jsonl")],
        "coin", 1, 1, instrumentation_level="light",
    )
    assert result == (0, False)
    assert json.loads(log.read_text()) == [
        "GENTIANS_GA_METRICS_PATH", "GENTIANS_INCREMENTAL_METRICS_PATH", "GENTIANS_TIMINGS_PATH",
    ]


def test_light_outputs_do_not_publish_unmeasured_dashboard_fields(tmp_path):
    from benchmarks.profile_baseline import write_outputs

    write_outputs(tmp_path, [], "light")
    assert not (tmp_path / "dashboard_data.json").exists()
    metadata = json.loads((tmp_path / "measurement.json").read_text())
    assert metadata["unmeasured"] == ["operator", "candidate", "quality", "clingo"]


def test_dashboard_uses_run_means_for_profile_counters(tmp_path):
    results = [
        RunResult("d", 1, 1, "run1", "ok", 0, 1.0, [], "{}", ""),
        RunResult("d", 2, 2, "run2", "ok", 0, 1.0, [], "{}", ""),
    ]
    write_dashboard_data(
        tmp_path,
        results,
        [],
        [],
        [],
        [
            {
                "dataset": "d",
                "run": 1,
                "metric": "clause_generation",
                "clauses": 100,
                "invented_predicates": 1,
                "invented_definition_clauses": 20,
                "invented_consumer_clauses": 30,
            },
            {
                "dataset": "d",
                "run": 2,
                "metric": "clause_generation",
                "clauses": 300,
                "invented_predicates": 1,
                "invented_definition_clauses": 40,
                "invented_consumer_clauses": 50,
            },
        ],
        [],
        [
            {
                "dataset": "d",
                "run": 1,
                "operation": "grounding",
                "operation_category": "grounding",
                "stats_atoms": 10,
                "stats_rules": 20,
            },
            {
                "dataset": "d",
                "run": 1,
                "operation": "solving",
                "operation_category": "solving",
                "models": 4,
            },
            {
                "dataset": "d",
                "run": 2,
                "operation": "solving",
                "operation_category": "solving",
                "models": 8,
            },
            {
                "dataset": "d",
                "run": 2,
                "operation": "solving",
                "operation_category": "solving",
                "models": 2,
            },
        ],
    )

    bench = json.loads((tmp_path / "dashboard_data.json").read_text())["benchmarks"][0]
    assert bench["algorithm"] == "steady_state"
    assert bench["candidates"] == 200
    assert bench["groundCalls"] == 1
    assert bench["solveCalls"] == 1.5
    assert bench["models"] == 7


def test_dashboard_uses_real_ga_diversity(tmp_path):
    write_dashboard_data(
        tmp_path,
        [
            RunResult(
                "d",
                1,
                1,
                "run",
                "ok",
                0,
                1.0,
                [],
                "{}",
                "",
            )
        ],
        [],
        [GAMetric("d", 1, 0, 1.0, 0.5, 1.0, 4, 2, 0.5, 1, 0.25, 2.0)],
        [],
        [],
        [],
        [],
    )

    run = json.loads((tmp_path / "dashboard_data.json").read_text())["benchmarks"][0][
        "fitnessRuns"
    ][0]
    assert run["points"] == [[0, 0.0, 0, 1.0, 0.5, 1.0, 0.5, 0.25, False]]
    fitness_chart = Path(".benchmarks/src/charts/FitnessChart.jsx").read_text(
        encoding="utf-8"
    )
    assert 'useState("mean")' in fitness_chart
    assert 'useState("generation")' in fitness_chart


def test_dashboard_reports_instrumentation_coverage(tmp_path):
    write_dashboard_data(
        tmp_path,
        [
            RunResult("d", 1, 1, "run", "ok", 0, 4.0, [], "{}", ""),
            RunResult("d", 2, 2, "run", "timeout", None, 10.0, [], "{}", ""),
        ],
        [TimingMetric("d", 1, "total_execution", 3.0, 1)],
        [],
        [],
        [],
        [],
        [],
    )

    payload = json.loads((tmp_path / "dashboard_data.json").read_text())
    benchmark = payload["benchmarks"][0]
    assert payload["schemaVersion"] == 12
    assert benchmark["total"] == 3.0
    assert benchmark["instrumentedRuns"] == 1
    assert "wall" not in benchmark
    assert "timeouts" not in benchmark


def test_ga_progress_exposes_round_time_and_evaluations(tmp_path):
    write_dashboard_data(
        tmp_path,
        [RunResult("d", 1, 1, "run", "ok", 0, 1.0, [], "{}", "")],
        [],
        [
            GAMetric(
                "d",
                1,
                2,
                3.0,
                2.0,
                3.0,
                elapsed_seconds=4.5,
                fitness_evaluations=27,
            )
        ],
        [],
        [],
        [],
        [],
    )

    run = json.loads((tmp_path / "dashboard_data.json").read_text())["benchmarks"][0][
        "fitnessRuns"
    ][0]
    assert run["points"] == [[2, 4.5, 27, 3.0, 2.0, 3.0, 0.0, 0.0, False]]


def test_dashboard_reports_largest_clause_space_per_run(tmp_path):
    rows = [
        {"dataset": "d", "run": run, "metric": "clause_generation", "clauses": clauses}
        for run, clauses in ((1, 10), (1, 40), (1, 25), (2, 20))
    ]
    write_dashboard_data(
        tmp_path,
        [RunResult("d", run, run, "run", "ok", 0, 1.0, [], "{}", "") for run in (1, 2)],
        [],
        [],
        [],
        rows,
        [],
        [],
    )

    bench = json.loads((tmp_path / "dashboard_data.json").read_text())["benchmarks"][0]
    assert bench["candidates"] == 30


def test_dashboard_summarizes_restarts_epochs_and_algorithm(tmp_path):
    arguments = json.dumps({"algorithm": "incremental"})
    write_dashboard_data(
        tmp_path,
        [RunResult("d", run, run, "run", "ok", 0, 1.0, [], arguments, "") for run in (1, 2)],
        [],
        [
            GAMetric("d", 1, 0, 1.0, 1.0, 1.0),
            GAMetric("d", 1, 1, 1.0, 1.0, 1.0, restarted=True),
            GAMetric("d", 1, 2, 1.0, 1.0, 1.0, restarted=True),
            GAMetric("d", 2, 0, 1.0, 1.0, 1.0),
        ],
        [],
        [],
        [],
        [],
        epoch_metrics=[
            {"dataset": "d", "run": 1, "reason": "generations", "active_clauses": 10,
             "generations": 50, "evaluations": 40},
            {"dataset": "d", "run": 1, "reason": "stagnation", "active_clauses": 30,
             "generations": 100, "evaluations": 80},
            {"dataset": "d", "run": 2, "reason": "solution", "active_clauses": 20,
             "generations": 30, "evaluations": 30},
        ],
    )

    bench = json.loads((tmp_path / "dashboard_data.json").read_text())["benchmarks"][0]
    assert bench["algorithm"] == "incremental"
    assert bench["restarts"] == 1
    assert [point[-1] for point in bench["fitnessRuns"][0]["points"]] == [False, True, True]
    epochs = bench["epochs"]
    assert epochs["runs"] == 2
    assert epochs["meanEpochs"] == 1.5
    assert {row["reason"]: row["meanCount"] for row in epochs["reasons"]} == {
        "generations": 0.5,
        "stagnation": 0.5,
        "space_exhausted": 0.0,
        "solution": 0.5,
        "generation_limit": 0.0,
    }
    assert epochs["meanActiveClauses"] == 20
    assert epochs["meanGenerations"] == 60


def test_steady_state_dashboard_has_no_epochs(tmp_path):
    write_dashboard_data(
        tmp_path,
        [RunResult("d", 1, 1, "run", "ok", 0, 1.0, [], "{}", "")],
        [],
        [],
        [],
        [],
        [],
        [],
    )

    bench = json.loads((tmp_path / "dashboard_data.json").read_text())["benchmarks"][0]
    assert bench["epochs"] is None
    assert bench["restarts"] == 0


def test_operator_summary_measures_lost_crossover_gains():
    rows = [
        {"dataset": "d", "run": 1, "operator": "mutation", "strategy": "random_group",
         "slots": 1, "crossover_strategy": "set_mix", "crossover_improved": improved,
         "lost_crossover_gain": lost}
        for improved, lost in ((True, True), (True, False), (True, False), (False, False))
    ]

    [summary] = operator_summary(rows)

    assert summary["crossover_strategy"] == "set_mix"
    assert summary["crossover_gain_events"] == 3
    assert summary["lost_crossover_gain_rate"] == pytest.approx(1 / 3)
    assert summary["retained_crossover_gain_rate"] == pytest.approx(2 / 3)


def test_dashboard_serializes_non_finite_fitness_as_null(tmp_path):
    write_dashboard_data(
        tmp_path,
        [
            RunResult(
                "even_odd",
                1,
                1,
                "run",
                "ok",
                0,
                1.0,
                [],
                "{}",
                "",
            )
        ],
        [],
        [GAMetric("even_odd", 1, 332, -0.02, float("-inf"), -0.02)],
        [],
        [],
        [],
        [],
    )

    payload = json.loads((tmp_path / "dashboard_data.json").read_text())

    assert payload["benchmarks"][0]["fitnessRuns"][0]["points"] == [
        [332, 0.0, 0, -0.02, None, -0.02, 0.0, 0.0, False]
    ]


def test_worker_resources_preserve_censored_and_final_snapshots(tmp_path):
    from benchmarks.process_resources import record_process_resources

    path = tmp_path / "resources.json"
    with record_process_resources(path):
        initial = json.loads(path.read_text(encoding="utf-8"))
        assert not initial["final"]
        assert initial["peak_rss_bytes"] > 0
    final = json.loads(path.read_text(encoding="utf-8"))
    assert final["final"]
    assert final["pid"] == initial["pid"]
    assert final["cpu_seconds"] >= initial["cpu_seconds"]
    assert final["peak_rss_bytes"] >= initial["peak_rss_bytes"]


def test_worker_resources_retries_transient_windows_file_lock(tmp_path, monkeypatch):
    from benchmarks.process_resources import record_process_resources
    from pathlib import Path

    original = Path.replace
    calls = []
    def replace(source, target):
        calls.append(True)
        if len(calls) == 1:
            raise PermissionError("temporary reader lock")
        return original(source, target)

    monkeypatch.setattr(Path, "replace", replace)
    with record_process_resources(tmp_path / "resources.json"):
        pass
    assert len(calls) >= 3
    assert json.loads((tmp_path / "resources.json").read_text(encoding="utf-8"))["final"]


def test_resource_snapshot_keeps_last_search_progress(tmp_path, monkeypatch):
    from gentians import timing
    from gentians.evolution.individual import Individual
    from benchmarks.process_resources import record_process_resources

    timing.reset()
    monkeypatch.setenv("GENTIANS_GA_METRICS_PATH", str(tmp_path / "ga.json"))
    path = tmp_path / "resources.json"
    try:
        assert timing.last_search_progress() is None
        with record_process_resources(path):
            timing.record_ga_generation(3, 2.0, [Individual(1, 2.0, False)],
                                        elapsed_seconds=0.1, fitness_evaluations=4)
            snapshot = timing.last_search_progress()
            assert snapshot is not None
            snapshot["generation"] = 99
            assert timing.last_search_progress()["generation"] == 3
        progress = json.loads(path.read_text(encoding="utf-8"))["search_progress"]
        assert progress["fitness_evaluations"] == 4
        assert progress["best_so_far"] == 2.0
    finally:
        timing.reset()


def test_progress_mean_carries_each_run_forward_on_every_axis():
    metrics = [
        GAMetric("d", 1, 0, 2.0, 1.0, 2.0, elapsed_seconds=0.0, fitness_evaluations=5),
        GAMetric("d", 1, 2, 6.0, 5.0, 6.0, elapsed_seconds=2.0, fitness_evaluations=9),
        GAMetric("d", 2, 0, 4.0, 3.0, 4.0, elapsed_seconds=0.0, fitness_evaluations=5),
        GAMetric("d", 2, 1, 8.0, 7.0, 8.0, elapsed_seconds=1.0, fitness_evaluations=7),
        GAMetric("d", 2, 2, 10.0, 9.0, 10.0, elapsed_seconds=2.0, fitness_evaluations=9),
    ]

    mean = dashboard_fitness_mean(metrics)

    assert mean["generation"]["max"] == [
        [0.0, 3.0, 2.0, 4.0],
        [1.0, 5.0, 2.0, 8.0],
        [2.0, 8.0, 6.0, 10.0],
    ]
    assert mean["generation"]["best"] == [[0.0, 4.0], [1.0, 8.0], [2.0, 10.0]]
    assert [row[0] for row in mean["evaluations"]["max"]] == [5.0, 7.0, 9.0]
    assert mean["seconds"]["avg"][-1] == [2.0, 7.0, 5.0, 9.0]


def test_progress_mean_uses_a_bounded_grid(monkeypatch):
    monkeypatch.setattr(profile, "MEAN_PROGRESS_POINTS", 5)
    metrics = [GAMetric("d", 1, generation, 1.0, 1.0, 1.0) for generation in range(101)]

    rows = dashboard_fitness_mean(metrics)["generation"]["max"]

    assert [row[0] for row in rows] == [0.0, 25.0, 50.0, 75.0, 100.0]


def test_thin_progress_keeps_improvements_restarts_and_the_last_point():
    points = [
        GAMetric("d", 1, generation, 1.0, 1.0, float(generation // 100),
                 restarted=generation == 333)
        for generation in range(1000)
    ]

    kept = thin_progress(points, limit=50)

    generations = [point.generation for point in kept]
    assert len(kept) <= 50
    assert generations == sorted(generations)
    assert {0, 999, 333}.issubset(generations)
    assert all(generation in generations for generation in range(100, 1000, 100))


def test_build_dashboard_reads_saved_run_artifacts(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    write_csv(tmp_path / "runs.csv", [{
        "arguments_json": json.dumps({"algorithm": "incremental"}), "command": "[]",
        "cprofile_path": "", "dataset": "d", "elapsed_seconds": 1.5,
        "experiment_id": "d_seed_1", "log_path": "x.log", "returncode": 0, "run": 1,
        "seed": 1, "status": "ok", "success": True,
    }])
    (runs / "d_run_1_timings.json").write_text(
        json.dumps([{"metric": "total_execution", "seconds": 1.25, "calls": 1}])
    )
    (runs / "d_run_1_ga_metrics.json").write_text(json.dumps([
        {"generation": 0, "max_fitness": 1.0, "avg_fitness": 1.0, "best_so_far": 1.0},
    ]))
    (runs / "d_run_1_incremental_metrics.jsonl").write_text(
        json.dumps({"reason": "solution", "active_clauses": 4}) + "\n"
    )
    compress_run_artifacts(tmp_path, "d", 1)

    build_dashboard(tmp_path)

    payload = json.loads((tmp_path / "dashboard_data.json").read_text())
    [bench] = payload["benchmarks"]
    assert payload["schemaVersion"] == 12
    assert bench["algorithm"] == "incremental"
    assert bench["total"] == 1.25
    assert bench["bestFoundRuns"] == 1
    assert bench["epochs"]["meanEpochs"] == 1
    assert bench["fitnessMean"]["generation"]["best"] == [[0.0, 1.0]]
