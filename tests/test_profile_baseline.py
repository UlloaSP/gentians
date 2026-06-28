from benchmarks.profile_baseline import (
    TimingMetric,
    dashboard_phases,
    operator_summary,
    parse_log,
)
from gentians import timing
from gentians.arguments import Arguments
from gentians.gentians import solve
from gentians.rule_generation.program import Program


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


def test_solve_exports_total_execution_after_phase_closes(monkeypatch):
    timing._totals.clear()
    timing._counts.clear()
    timing._stack.clear()
    monkeypatch.setattr(timing, "_enabled", True)
    exported = {}

    monkeypatch.setattr(
        "gentians.gentians.build_hypothesis_space",
        lambda program, arguments: ["rule."],
    )
    monkeypatch.setattr(
        "gentians.gentians.genetic_solver",
        lambda *args, **kwargs: (["rule."], 1.0, True),
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


def test_dashboard_prefers_exported_exclusive_self_time():
    phases = dashboard_phases(
        [
            TimingMetric("d", 1, "hypothesis_space", 10.0, 1),
            TimingMetric("d", 1, "hypothesis_space.self", 2.0, 1),
            TimingMetric("d", 1, "hypothesis_space.grounding", 3.0, 1),
            TimingMetric("d", 1, "hypothesis_space.solving", 4.0, 1),
        ]
    )

    assert phases["hypothesisSpace"]["self"] == 2.0
