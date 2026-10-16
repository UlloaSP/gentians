"""Timeouts retain completed evaluations and readable benchmark instrumentation."""

import gzip
import json
import sys
from pathlib import Path

import pytest

from benchmarks import profile_baseline as profile
from gentians import Arguments, timing


def run_worker(tmp_path: Path, code: str, timeout: int):
    return profile.run_streamed(
        [sys.executable, "-c", code], "{}", tmp_path / "d_run_1.log", timeout,
        *[tmp_path / f"d_run_1{suffix}" for suffix in (
            "_timings.json", "_ga_metrics.json", "_operator_metrics.jsonl",
            "_candidate_metrics.jsonl", "_quality_metrics.jsonl", "_clingo_metrics.jsonl",
        )], "d", 1, 43,
    )


@pytest.mark.parametrize("algorithm", ["steady_state", "incremental"])
def test_timeout_returns_best_and_exports_both_algorithms(tmp_path, algorithm):
    # Contradictory examples prevent a solution; supplied clauses isolate search
    # and profiling from clause-generation duration.
    code = f"""
import json, os
from benchmarks import profile_baseline as profile
from gentians import Arguments
from gentians.gentians import solve
from tests.task_helpers import example, inductive_task, make_clause_space
task = inductive_task(
    [f'q{{i}}(a).' for i in range(50)],
    [example(('p(a)', ''), True)], [example(('p(a)', ''), False)], [], [],
    max_program_clauses=3,
)
space = make_clause_space([f'p(a) :- q{{i}}(a).' for i in range(50)])
args = Arguments(algorithm={algorithm!r}, random_seed=43)
os.environ['GENTIANS_ARGUMENTS_JSON'] = json.dumps(args.__dict__)
profile.gentians_main = lambda arguments: solve(task, arguments, space)
profile.run_profile_worker()
"""
    returncode, timed_out = run_worker(tmp_path, code, 2)

    assert timed_out and returncode == 124
    parsed = profile.parse_log(tmp_path / "d_run_1.log")
    assert parsed["best_program"] and not parsed["success"]
    assert (tmp_path / "d_run_1_hypothesis.lp").read_text().strip()
    resources = json.loads((tmp_path / "d_run_1_resources.json").read_text())
    assert resources["final"]
    timings = profile.read_timings(tmp_path / "d_run_1_timings.json", "d", 1)
    assert next(row.seconds for row in timings if row.metric == "total_execution") > 0
    assert profile.read_ga_metrics(tmp_path / "d_run_1_ga_metrics.json", "d", 1)
    for kind in ("operator", "candidate", "quality", "clingo"):
        rows = profile.read_jsonl_rows(
            tmp_path / f"d_run_1_{kind}_metrics.jsonl", "d", 1, 43, "d_seed_43",
        )
        assert rows, kind
        if kind == "operator":
            assert {row["operator"] for row in rows} >= {"crossover", "mutation"}

    runs = tmp_path / "runs"
    runs.mkdir()
    for path in list(tmp_path.glob("d_run_1*")):
        path.rename(runs / path.name)
    result = profile.RunResult(
        "d", 1, 43, "d_seed_43", "timeout", 124, 2.0, [],
        json.dumps({"algorithm": algorithm}), str(runs / "d_run_1.log"),
    )
    profile.compress_run_artifacts(tmp_path, "d", 1)
    profile.write_outputs(tmp_path, [result], "full")
    dashboard = json.loads((tmp_path / "dashboard_data.json").read_text())
    [benchmark] = dashboard["benchmarks"]
    assert benchmark["instrumentedRuns"] == 1
    assert benchmark["operatorSummary"]
    assert benchmark["fitnessRuns"]
    with gzip.open(runs / "d_run_1_hypothesis.lp.gz", "rt") as file:
        assert file.read().strip()


@pytest.mark.parametrize("stream_events", [False, True])
def test_forced_timeout_keeps_periodic_metrics_without_finalizers(tmp_path, stream_events):
    code = f"""
import time
from types import SimpleNamespace
from gentians import timing
with timing.phase('total_execution'):
    timing.record_metric('operator', {{'operator': 'mutation', 'improved': True}})
    timing.record_ga_generation(0, 1.0, [SimpleNamespace(score=1.0, genome=1)])
    started = time.monotonic()
    while {stream_events!r} and time.monotonic() - started < 1.2:
        timing.record_metric('operator', {{'operator': 'mutation', 'improved': True}})
        time.sleep(0.01)
    print('hung operation', flush=True)
    time.sleep(100)
"""
    returncode, timed_out = run_worker(tmp_path, code, 2)

    assert timed_out and returncode != 0
    assert "hung operation" in (tmp_path / "d_run_1.log").read_text()
    assert profile.read_ga_metrics(tmp_path / "d_run_1_ga_metrics.json", "d", 1)
    assert profile.read_jsonl_rows(
        tmp_path / "d_run_1_operator_metrics.jsonl", "d", 1, 43, "d_seed_43",
    )
    timings = profile.read_timings(tmp_path / "d_run_1_timings.json", "d", 1)
    assert next(row.seconds for row in timings if row.metric == "total_execution") > 0


def test_open_phase_checkpoints_do_not_change_final_totals(tmp_path, monkeypatch):
    timing.reset()
    monkeypatch.setattr(timing, "_enabled", True)
    path = tmp_path / "timings.json"
    monkeypatch.setenv("GENTIANS_TIMINGS_PATH", str(path))
    clock = [10.0]
    monkeypatch.setattr(timing.time, "perf_counter", lambda: clock[0])
    try:
        with timing.phase("outer"):
            clock[0] = 12.0
            with timing.phase("inner"):
                with timing.instrumentation():
                    clock[0] = 14.0
                clock[0] = 16.0
                with timing.instrumentation():
                    timing.export()
                    partial = {r.metric: r.seconds for r in profile.read_timings(path, "d", 1)}
                    assert partial == {"outer": 4.0, "outer.self": 2.0,
                                       "inner": 2.0, "inner.self": 2.0}
                    assert "outer" not in timing._totals
                    clock[0] = 18.0
            clock[0] = 20.0
        timing.export()
        final = profile.read_timings(path, "d", 1)
        assert {r.metric: r.seconds for r in final} == {
            "outer": 6.0, "outer.self": 4.0, "inner": 2.0, "inner.self": 2.0,
        }
        assert all(r.calls == 1 for r in final)
    finally:
        timing.reset()


def test_jsonl_batches_bound_memory_and_preserve_all_events(tmp_path):
    timing.reset()
    path = tmp_path / "operators.jsonl"
    try:
        timing.append_jsonl(str(path), [{"event": i} for i in range(2500)])
        assert path.exists()
        assert len(timing._jsonl_rows[str(path)]) < 1024
        timing.export()
        assert [json.loads(line)["event"] for line in path.read_text().splitlines()] == list(range(2500))
    finally:
        timing.reset()


def test_crash_during_timeout_grace_is_still_a_failure(tmp_path):
    assert run_worker(tmp_path, "import sys,time; time.sleep(1.2); sys.exit(7)", 1) == (7, False)


@pytest.mark.parametrize("delay", [1.2, 6.2])
def test_slow_parent_logging_does_not_turn_success_into_timeout(tmp_path, monkeypatch, delay):
    import time

    monkeypatch.setattr(profile, "print", lambda *args, **kwargs: time.sleep(delay), raising=False)
    assert run_worker(tmp_path, "print('done', flush=True)", 1) == (0, False)


@pytest.mark.parametrize("algorithm", ["steady_state", "incremental"])
def test_timeout_during_initialization_returns_completed_evaluation(monkeypatch, algorithm):
    from gentians.algorithms import incremental_clause_genetic_search, steady_state_genetic_search
    from gentians.evaluation.evaluator import CandidateEvaluator
    from tests.task_helpers import example, inductive_task, make_clause_space

    clock = [10.0]
    monkeypatch.setattr("gentians.search.budget.time.monotonic", lambda: clock[0])
    monkeypatch.setenv("GENTIANS_RUN_DEADLINE", "12.0")
    original = CandidateEvaluator.__call__
    evaluated = []

    def finish_evaluation_at_deadline(self, candidate):
        result = original(self, candidate)
        evaluated.append((tuple(map(str, candidate)), result.score))
        clock[0] = 13.0
        return result

    monkeypatch.setattr(CandidateEvaluator, "__call__", finish_evaluation_at_deadline)
    searches = {"steady_state": steady_state_genetic_search, "incremental": incremental_clause_genetic_search}
    task = inductive_task([], [example(("p", ""), True)], [], [], [])
    result = searches[algorithm](Arguments(random_seed=43), task, make_clause_space(["p.", "q."]))
    assert evaluated == [(result.hypothesis, result.score)]


def test_net_timeout_before_first_evaluation_is_not_a_wall_timeout(monkeypatch):
    from gentians.search.budget import SearchBudget

    monkeypatch.setenv("GENTIANS_RUN_DEADLINE", "100.0")
    monkeypatch.setattr("gentians.search.budget.time.monotonic", lambda: 10.0)
    budget = SearchBudget(1)
    with pytest.raises(RuntimeError, match="before any candidate"):
        budget.result()
