import json
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace

from benchmarks.profile_baseline import (
    GAMetric,
    RunResult,
    TimingMetric,
    clingo_summary,
    dashboard_phases,
    dashboard_quality,
    operator_summary,
    parse_log,
    reset_run_outputs,
    run_profile_worker,
    run_streamed,
    write_dashboard_data,
    write_debug_clingo_program,
)
from gentians import timing
from gentians.arguments import Arguments
from gentians.gentians import solve
from gentians.clauses.program import Program
from gentians.clauses.rule_space import RuleSpace


def test_profile_worker_applies_seed_to_arguments(monkeypatch):
    captured = {}
    monkeypatch.setenv("GENTIANS_ARGUMENTS_JSON", json.dumps(Arguments().__dict__))
    monkeypatch.setenv("GENTIANS_RANDOM_SEED", "17")
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
    assert "pos_exs(0..0)." in dump
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
    assert summary["improvement_rate"] == 0.5
    assert summary["mean_score_delta"] == 1.0


def test_operator_summary_measures_lost_crossover_gain_per_run():
    [summary] = operator_summary(
        [
            {
                "dataset": "d",
                "run": 1,
                "operator": "mutation",
                "strategy": "random_group",
                "crossover_strategy": "set_mix",
                "crossover_improved": True,
                "lost_crossover_gain": True,
            },
            {
                "dataset": "d",
                "run": 2,
                "operator": "mutation",
                "strategy": "random_group",
                "crossover_strategy": "set_mix",
                "crossover_improved": True,
                "lost_crossover_gain": False,
            },
            {
                "dataset": "d",
                "run": 2,
                "operator": "mutation",
                "strategy": "random_group",
                "crossover_strategy": "set_mix",
                "crossover_improved": True,
                "lost_crossover_gain": False,
            },
        ]
    )

    assert summary["crossover_strategy"] == "set_mix"
    assert summary["crossover_gain_events"] == 1.5
    assert summary["lost_crossover_gain_rate"] == 0.5
    assert summary["retained_crossover_gain_rate"] == 0.5


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
            "key": "consistent",
            "rate": 75,
            "meanCount": 1,
            "count": 2,
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


def test_solve_exports_total_execution_after_phase_closes(monkeypatch):
    timing.reset()
    monkeypatch.setattr(timing, "_enabled", True)
    exported = {}

    monkeypatch.setattr(
        "gentians.gentians.search_solver",
        lambda *args, **kwargs: (("rule.",), 1.0, True),
    )

    def export():
        exported.update(timing._totals)

    monkeypatch.setattr("gentians.gentians.export_timings", export)

    solve(
        Program([], [], [], [], []),
        Arguments(population={"name": "random", "size": 1}),
    )

    assert "total_execution" in exported
    assert timing._stack == []
    timing.reset()


def test_total_execution_excludes_result_output(monkeypatch):
    timing.reset()
    monkeypatch.setattr(timing, "_enabled", True)
    monkeypatch.setattr(
        "gentians.gentians.search_solver",
        lambda *args, **kwargs: (("rule.",), 1.0, True),
    )
    monkeypatch.setattr("gentians.gentians.export_timings", lambda: None)
    monkeypatch.setattr("builtins.print", lambda *args, **kwargs: time.sleep(0.02))

    solve(
        Program([], [], [], [], []),
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
        return ("rule.",), 1.0, True

    def print_result(*args, **_kwargs):
        output.append(args)
        clock[0] += 20.0

    monkeypatch.setattr("gentians.gentians.search_solver", search)
    monkeypatch.setattr("gentians.gentians.export_timings", lambda: None)
    monkeypatch.setattr("gentians.gentians.time.time", lambda: clock[0])
    monkeypatch.setattr("builtins.print", print_result)

    solve(
        Program([], [], [], [], []),
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
        [SimpleNamespace(score=1.0, program=1)],
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


def test_dashboard_has_pregrounding_phase():
    phases = dashboard_phases(
        [
            TimingMetric("d", 1, "total_execution", 10.0, 1),
            TimingMetric("d", 1, "pregrounding", 4.0, 1),
            TimingMetric("d", 1, "pregrounding.self", 4.0, 1),
            TimingMetric("d", 1, "pregrounding.grounding", 3.0, 1),
        ]
    )

    assert phases["pregrounding"]["grounding"] == 3.0
    assert phases["pregrounding"]["python"] == 1.0


def test_dashboard_attributes_fitness_cost_to_operator_phase():
    phases = dashboard_phases(
        [
            TimingMetric("d", 1, "total_execution", 20.0, 1),
            TimingMetric("d", 1, "hypothesis_space.self", 5.0, 1),
            TimingMetric("d", 1, "hypothesis_space.grounding", 1.0, 1),
            TimingMetric("d", 1, "hypothesis_space.solving", 2.0, 1),
            TimingMetric("d", 1, "initialization.self", 10.0, 2),
            TimingMetric("d", 1, "initialization.grounding", 3.0, 2),
            TimingMetric("d", 1, "initialization.solving", 4.0, 2),
            TimingMetric("d", 1, "initialization.closure", 1.0, 2),
            TimingMetric("d", 1, "search.self", 5.0, 1),
        ]
    )

    assert phases["hypothesisSpace"] == {
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

    reset_run_outputs(paths)

    assert all(not path.exists() for path in paths)


def test_run_streamed_sets_dataset_and_run_env(tmp_path):
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
        10,
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
                "metric": "hypothesis_space",
                "clauses": 100,
                "invented_predicates": 1,
                "invented_definition_clauses": 20,
                "invented_consumer_clauses": 30,
            },
            {
                "dataset": "d",
                "run": 2,
                "metric": "hypothesis_space",
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
    assert run["points"] == [[0, 0.0, 0, 1.0, 0.5, 1.0, 0.5, 0.25]]
    fitness_chart = Path(".benchmarks/src/charts/FitnessChart.jsx").read_text(
        encoding="utf-8"
    )
    assert 'useState("mean")' in fitness_chart
    assert 'name: "generación"' in fitness_chart
    assert "fitnessEvaluations" not in fitness_chart
    assert "elapsedSeconds" not in fitness_chart


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
    assert payload["schemaVersion"] == 7
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
    assert run["points"] == [[2, 4.5, 27, 3.0, 2.0, 3.0, 0.0, 0.0]]


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
        [332, 0.0, 0, -0.02, None, -0.02, 0.0, 0.0]
    ]
