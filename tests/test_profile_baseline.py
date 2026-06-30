import json
import re
from pathlib import Path

from benchmarks.profile_baseline import (
    GAMetric,
    RunResult,
    TimingMetric,
    clingo_summary,
    compute_accounting_invariants,
    dashboard_phases,
    operator_summary,
    parse_log,
    reset_run_outputs,
    write_dashboard_data,
)
from gentians import timing
from gentians.arguments import Arguments
from gentians.gentians import solve
from gentians.rule_generation.program import Program
from gentians.rule_generation.rule_space import RuleSpace


def test_parse_log_marks_only_found_best_as_success(tmp_path):
    log = tmp_path / "run.log"
    log.write_text(
        "--- Found best program with score 1.0 ---\n"
        "rule.\n"
        "Total time: 0.1\n",
        encoding="utf-8",
    )

    parsed = parse_log(log, "dataset", 1)

    assert parsed["success"] is True


def test_parse_log_keeps_best_candidate_as_not_success(tmp_path):
    log = tmp_path / "run.log"
    log.write_text(
        "--- Best candidate program with score 1.0 ---\n"
        "rule.\n"
        "Total time: 0.1\n",
        encoding="utf-8",
    )

    parsed = parse_log(log, "dataset", 1)

    assert parsed["success"] is False


def test_operator_summary_sanitizes_non_finite_scores():
    rows = [
        {
            "dataset": "coin",
            "operator": "mutation",
            "strategy": "x",
            "new_score": "nan",
            "original_score": "1",
            "children": 1,
        }
    ]

    [summary] = operator_summary(rows)

    assert summary["mean_score_delta"] == -1.0


def test_operator_summary_separates_crossover_duplicate_types():
    rows = [
        {
            "dataset": "d",
            "operator": "crossover",
            "strategy": "set_mix",
            "not_applied": True,
            "children": 2,
            "children_same_as_parent": 2,
            "children_duplicate_population": 0,
            "children_improved": 0,
            "parent_a_score": 3,
            "parent_b_score": 2,
            "child_1_score": 3,
            "child_2_score": 2,
        },
        {
            "dataset": "d",
            "operator": "crossover",
            "strategy": "set_mix",
            "not_applied": False,
            "children": 2,
            "children_same_as_parent": 1,
            "children_duplicate_population": 1,
            "children_improved": 1,
            "parent_a_score": 3,
            "parent_b_score": 2,
            "child_1_score": 5,
            "child_2_score": 1,
        },
    ]

    [summary] = operator_summary(rows)

    assert summary["not_applied_rate"] == 0.5
    assert summary["same_as_parent_rate"] == 0.75
    assert summary["duplicate_rate"] == 0.25
    assert summary["improvement_rate"] == 0.25
    assert summary["mean_score_delta"] == -0.25


def test_operator_summary_counts_mutation_population_duplicates():
    rows = [
        {
            "dataset": "d",
            "operator": "mutation",
            "strategy": "random_group",
            "duplicate_population": True,
        }
    ]

    [summary] = operator_summary(rows)

    assert summary["duplicate_rate"] == 1.0


def test_solve_exports_total_execution_after_phase_closes(monkeypatch):
    timing._totals.clear()
    timing._counts.clear()
    timing._stack.clear()
    monkeypatch.setattr(timing, "_enabled", True)
    exported = {}

    monkeypatch.setattr(
        "gentians.gentians.build_hypothesis_space",
        lambda program, arguments: RuleSpace.from_clauses(["rule."]),
    )
    monkeypatch.setattr(
        "gentians.gentians.genetic_solver",
        lambda *args, **kwargs: ([0], 1.0, True),
    )
    monkeypatch.setattr("gentians.gentians.create_fitness", lambda *args: object())
    monkeypatch.setattr("gentians.gentians.create_population", lambda *args: object())
    monkeypatch.setattr("gentians.gentians.create_selection", lambda *args: object())
    monkeypatch.setattr("gentians.gentians.create_crossover", lambda *args: object())
    monkeypatch.setattr("gentians.gentians.create_mutation", lambda *args: object())
    monkeypatch.setattr("gentians.gentians.create_replacement", lambda *args: object())

    def export():
        exported.update(timing._totals)

    monkeypatch.setattr("gentians.gentians.export_timings", export)

    solve(Program([], [], [], [], []), Arguments())

    assert "total_execution" in exported
    assert timing._stack == []
    timing._totals.clear()
    timing._counts.clear()


def test_phase_records_exclusive_self_time(monkeypatch):
    timing._totals.clear()
    timing._counts.clear()
    timing._stack.clear()
    monkeypatch.setattr(timing, "_enabled", True)

    with timing.phase("outer"):
        with timing.phase("inner"):
            pass

    assert "outer.self" in timing._totals
    assert "inner.self" in timing._totals
    assert timing._totals["outer.self"] <= timing._totals["outer"]
    timing._totals.clear()
    timing._counts.clear()


def test_dashboard_attributes_nested_python_to_phase_self_time():
    phases = dashboard_phases(
        [
            TimingMetric("d", 1, "hypothesis_space", 10.0, 1),
            TimingMetric("d", 1, "hypothesis_space.self", 2.0, 1),
            TimingMetric("d", 1, "hypothesis_space.grounding", 3.0, 1),
            TimingMetric("d", 1, "hypothesis_space.solving", 4.0, 1),
        ]
    )

    assert phases["hypothesisSpace"]["self"] == 3.0


def test_dashboard_attributes_genetic_self_to_ga_python():
    phases = dashboard_phases(
        [
            TimingMetric("d", 1, "total_execution", 10.0, 1),
            TimingMetric("d", 1, "genetic.self", 3.0, 1),
            TimingMetric("d", 1, "selection", 2.0, 1),
            TimingMetric("d", 1, "selection.self", 2.0, 1),
            TimingMetric("d", 1, "replacement", 5.0, 1),
            TimingMetric("d", 1, "replacement.self", 5.0, 1),
        ]
    )

    assert phases["gaPython"]["self"] == 3.0
    assert phases["replacement"]["self"] == 5.0
    assert "other" not in phases


def test_dashboard_has_fitness_setup_phase():
    phases = dashboard_phases(
        [
            TimingMetric("d", 1, "total_execution", 10.0, 1),
            TimingMetric("d", 1, "fitness.setup", 4.0, 1),
            TimingMetric("d", 1, "fitness.setup.grounding", 3.0, 1),
        ]
    )

    assert phases["fitnessSetup"]["grounding"] == 3.0
    assert phases["fitnessSetup"]["self"] == 1.0


def test_frontend_phase_order_matches_dashboard_phases():
    metrics_js = Path(".benchmarks/src/metrics.js").read_text(encoding="utf-8")
    match = re.search(r"phaseOrder = \[(.*?)\]\n\nexport const typeOrder", metrics_js, re.S)
    assert match is not None
    frontend_phases = re.findall(r"\['([^']+)'", match.group(1))

    backend_phases = dashboard_phases([]).keys()

    assert set(frontend_phases) == set(backend_phases)


def test_accounting_invariants_include_fitness_setup():
    rows = compute_accounting_invariants(
        "d",
        1,
        [
            TimingMetric("d", 1, "total_execution", 10.0, 1),
            TimingMetric("d", 1, "hypothesis_space", 2.0, 1),
            TimingMetric("d", 1, "fitness.setup", 3.0, 1),
            TimingMetric("d", 1, "fitness.setup.grounding", 2.5, 1),
            TimingMetric("d", 1, "genetic", 5.0, 1),
        ],
    )

    by_name = {row["invariant"]: row for row in rows}

    assert by_name["total_vs_top_level"]["right_seconds"] == 10.0
    assert by_name["fitness.setup_contains_clingo"]["right_seconds"] == 2.5


def test_clingo_summary_uses_categories_and_mean_models_from_zero():
    [summary] = clingo_summary(
        [
            {
                "dataset": "d",
                "operation": "fixed_presolve",
                "operation_category": "solving",
                "phase_context": "mutation.fitness",
                "seconds": 0.2,
                "models": 2,
            }
        ]
    )

    assert summary["operation_category"] == "solving"
    assert summary["mean_models"] == 2
    assert summary["mean_models_points"][0] == [0, 0.0]


def test_dashboard_aggregates_clingo_by_category_and_max_ground_size(tmp_path):
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
                "",
            )
        ],
        [],
        [],
        [],
        [],
        [],
        [],
        [
            {
                "dataset": "d",
                "run": 1,
                "operation": "fixed_preground",
                "operation_category": "grounding",
                "phase_context": "fitness.setup",
                "seconds": 0.5,
                "stats_atoms": 10,
                "stats_rules": 20,
            },
            {
                "dataset": "d",
                "run": 1,
                "operation": "fixed_presolve",
                "operation_category": "solving",
                "phase_context": "mutation.fitness",
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
    assert bench["atoms"] == 10
    assert bench["groundRules"] == 20
    assert bench["models"] == 3


def test_reset_run_outputs_removes_stale_profile_files(tmp_path):
    paths = [tmp_path / "a.jsonl", tmp_path / "b.json"]
    for path in paths:
        path.write_text("stale", encoding="utf-8")

    reset_run_outputs(paths)

    assert all(not path.exists() for path in paths)


def test_dashboard_uses_run_means_for_profile_counters(tmp_path):
    results = [
        RunResult("d", 1, 1, "run1", "ok", 0, 1.0, [], "{}", "", ""),
        RunResult("d", 2, 2, "run2", "ok", 0, 1.0, [], "{}", "", ""),
    ]
    write_dashboard_data(
        tmp_path,
        results,
        [],
        [],
        [],
        [],
        [
            {"dataset": "d", "run": 1, "metric": "hypothesis_space", "clauses": 100},
            {"dataset": "d", "run": 2, "metric": "hypothesis_space", "clauses": 300},
        ],
        [],
        [
            {
                "dataset": "d",
                "run": 1,
                "operation": "fixed_preground",
                "operation_category": "grounding",
                "stats_atoms": 10,
                "stats_rules": 20,
            },
            {
                "dataset": "d",
                "run": 1,
                "operation": "fixed_presolve",
                "operation_category": "solving",
                "models": 4,
            },
            {
                "dataset": "d",
                "run": 2,
                "operation": "fixed_presolve",
                "operation_category": "solving",
                "models": 8,
            },
            {
                "dataset": "d",
                "run": 2,
                "operation": "fixed_presolve",
                "operation_category": "solving",
                "models": 2,
            },
        ],
    )

    bench = json.loads((tmp_path / "dashboard_data.json").read_text())["benchmarks"][0]
    assert bench["candidates"] == 200
    assert bench["groundCalls"] == 0.5
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
                "",
            )
        ],
        [],
        [GAMetric("d", 1, 0, 0, 1.0, 0.5, 1.0, 4, 2, 0.5, 1, 0.25, 2.0)],
        [],
        [],
        [],
        [],
        [],
    )

    run = json.loads((tmp_path / "dashboard_data.json").read_text())["benchmarks"][0][
        "fitnessRuns"
    ][0]
    assert run["diversity"] == [[0, 0.5]]
    assert run["invalid"] == [[0, 0.25]]


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
                "",
            )
        ],
        [],
        [GAMetric("even_odd", 1, 332, 332, -0.02, float("-inf"), -0.02)],
        [],
        [],
        [],
        [],
        [],
    )

    payload = json.loads((tmp_path / "dashboard_data.json").read_text())

    assert payload["benchmarks"][0]["fitnessRuns"][0]["avgArr"] == [[332, None]]
