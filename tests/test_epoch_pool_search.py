import gc
import weakref

import pytest

from gentians import gentians as entrypoint
from gentians.algorithms import epoch_pool_genetic as pool_search
from gentians.algorithms.result import SearchResult
from gentians.arguments import Arguments
from gentians.algorithms.epoch_pool_genetic import epoch_pool_genetic_search
from gentians.evaluation import pool_solver
from gentians.evaluation.evaluator import CandidateEvaluator
from gentians.evolution.reproduction import ReproductiveHistory
from tests.task_helpers import example, inductive_task, make_clause_space


def test_epoch_pool_search_rebuilds_and_returns_program_from_global_space(monkeypatch):
    evaluator_calls = []
    population_sizes = []
    create_evaluator = pool_search.create_epoch_pool_evaluator
    monkeypatch.setattr(
        pool_search,
        "create_epoch_pool_evaluator",
        lambda *args, **kwargs: (
            evaluator_calls.append(1) or create_evaluator(*args, **kwargs)
        ),
    )
    monkeypatch.setattr(
        pool_search,
        "record_ga_generation",
        lambda _generation, _best, population, **_kwargs: population_sizes.append(
            len(population)
        ),
    )
    task = inductive_task(
        [],
        [example(("target(z)", ""), True)],
        [],
        [],
        [],
        max_program_clauses=2,
    )
    space = make_clause_space(["target(a).", "target(b).", "other(a)."])
    arguments = Arguments(
        evaluation={"scoring": "cov_program", "constraint_inheritance": False},
        iterations_genetic=5,
        random_seed=4,
        clause_pool={
            "enabled": True,
            "size": 2,
            "epoch_generations": 1,
            "elite_count": 2,
        },
    )
    arguments.population["size"] = 3

    result = epoch_pool_genetic_search(
        arguments,
        task,
        space,
    )

    assert set(result.hypothesis) <= set(space.clauses)
    assert len(evaluator_calls) == 5
    assert set(population_sizes) == {3}


@pytest.mark.parametrize("enabled", [False, True])
def test_solve_selects_configured_search(monkeypatch, enabled):
    calls = []
    result = SearchResult(("target(a).",), 1.0, True)
    monkeypatch.setattr(
        entrypoint,
        "steady_state_genetic_search",
        lambda *args: calls.append("steady") or result,
    )
    monkeypatch.setattr(
        entrypoint,
        "epoch_pool_genetic_search",
        lambda *args: calls.append("pool") or result,
    )
    arguments = Arguments()
    arguments.clause_pool["enabled"] = enabled

    entrypoint.solve(inductive_task([], [], [], [], []), arguments)

    assert calls == ["pool" if enabled else "steady"]


@pytest.mark.parametrize(
    "config",
    [
        {"enabled": True, "size": 0, "epoch_generations": 1, "elite_count": 1},
        {"enabled": True, "size": 1, "epoch_generations": True, "elite_count": 1},
        {"enabled": True, "size": 1, "epoch_generations": 1, "elite_count": 4},
    ],
)
def test_epoch_pool_search_rejects_invalid_config(config):
    arguments = Arguments(
        evaluation={"scoring": "cov_program", "constraint_inheritance": False},
        iterations_genetic=1,
        population={"name": "random", "size": 3},
        clause_pool=config,
    )

    with pytest.raises(ValueError, match="clause_pool"):
        epoch_pool_genetic_search(
            arguments,
            inductive_task([], [], [], [], []),
            make_clause_space(["target(a)."]),
        )


def _general_pool_task():
    task = inductive_task(
        ["edge(a,b)."],
        [
            example(("target(a)", "blocked(a)", "seed(a)."), True),
            example(("target(z)", ""), True),
        ],
        [example(("target(b)", "", "seed(b)."), False)],
        [],
        [],
        max_program_clauses=3,
    )
    space = make_clause_space(
        [
            "reach(X) :- seed(X).",
            "reach(Y) :- reach(X), edge(X,Y).",
            "target(X) :- reach(X), not blocked(X).",
            "blocked(a).",
            "blocked(b).",
            "target(a); blocked(a).",
        ]
    )
    return task, space


def _pool_arguments(**overrides):
    return Arguments(
        evaluation={"scoring": "cov_program", "constraint_inheritance": False},
        iterations_genetic=8,
        random_seed=17,
        population={"name": "random", "size": 4},
        clause_pool={
            "enabled": True,
            "size": 4,
            "epoch_generations": 2,
            "elite_count": 2,
            **overrides,
        },
    )


@pytest.mark.parametrize(
    "policies",
    [
        {},
        {"retention": "behavior", "filling": "neighbors"},
        {"retention": "reproductive"},
        {"retention": "reproductive", "filling": "neighbors"},
    ],
)
def test_pool_solver_choice_preserves_candidate_sequence_and_progress(
    monkeypatch, policies
):
    task, space = _general_pool_task()
    evaluated = []
    progress = []
    evaluate = CandidateEvaluator.__call__

    def record_evaluation(self, candidate):
        result = evaluate(self, candidate)
        evaluated.append((candidate, result))
        return result

    def record_progress(generation, best, population, **metrics):
        progress.append(
            (generation, best, tuple(population), metrics["fitness_evaluations"])
        )

    monkeypatch.setattr(CandidateEvaluator, "__call__", record_evaluation)
    monkeypatch.setattr(pool_search, "record_ga_generation", record_progress)
    fresh = epoch_pool_genetic_search(
        _pool_arguments(solver="fresh", **policies), task, space
    )
    fresh_evaluated, fresh_progress = list(evaluated), list(progress)
    evaluated.clear()
    progress.clear()
    persistent = epoch_pool_genetic_search(
        _pool_arguments(solver="persistent", **policies), task, space
    )
    assert persistent == fresh
    assert evaluated == fresh_evaluated
    assert progress == fresh_progress
    assert [row[0] for row in progress] == list(range(9))
    assert not persistent.is_solution


def test_epoch_rebuild_compiles_coverage_once_and_accounts_for_work(monkeypatch):
    task, space = _general_pool_task()
    rows = []
    progress = []
    compilation_calls = []
    compile_coverage = pool_search.compile_coverage_program

    def compile_once(*args):
        compilation_calls.append(1)
        return compile_coverage(*args)

    def unexpected_compile(*args):
        pytest.fail("pool constructor recompiled coverage")

    monkeypatch.setattr(pool_search, "compile_coverage_program", compile_once)
    monkeypatch.setattr(pool_solver, "compile_coverage_program", unexpected_compile)
    monkeypatch.setattr(pool_search, "metric_enabled", lambda kind: kind == "pool")
    monkeypatch.setattr(
        pool_search, "record_metric", lambda kind, row: rows.append(row)
    )
    monkeypatch.setattr(
        pool_search,
        "record_ga_generation",
        lambda generation, best, population, **metrics: progress.append(metrics),
    )
    epoch_pool_genetic_search(_pool_arguments(), task, space)
    assert len(compilation_calls) == 1
    assert [row["epoch"] for row in rows] == [0, 1, 2, 3]
    assert [row["reason"] for row in rows] == ["generations"] * 3 + ["generation_limit"]
    assert sum(row["generations"] for row in rows) == 8
    assert (
        sum(row["evaluations"] for row in rows) == progress[-1]["fitness_evaluations"]
    )
    assert all(row["duplicates"] <= row["generations"] for row in rows)
    assert all(row["pool_size"] > 0 for row in rows)
    assert all(
        row["build_seconds"] >= 0 and row["solver_setup_seconds"] >= 0 for row in rows
    )


def test_epoch_search_observes_reproduction_and_decays_history_on_renewal(monkeypatch):
    task, space = _general_pool_task()
    attempts = []
    decays = []
    observe = ReproductiveHistory.observe
    decay = ReproductiveHistory.decay

    def record_observation(self, first, second, child, duplicate=False):
        attempts.append((first, second, child, duplicate))
        observe(self, first, second, child, duplicate)

    def record_decay(self, factor=0.5):
        decays.append(factor)
        decay(self, factor)

    monkeypatch.setattr(ReproductiveHistory, "observe", record_observation)
    monkeypatch.setattr(ReproductiveHistory, "decay", record_decay)
    epoch_pool_genetic_search(_pool_arguments(retention="reproductive"), task, space)
    assert len(attempts) == 8
    assert len(decays) == 3
    assert all(child is None for _, _, child, duplicate in attempts if duplicate)


@pytest.mark.parametrize("solution_stage", ["initialization", "refill"])
def test_epoch_search_stops_evaluating_at_first_perfect_candidate(
    monkeypatch, solution_stage
):
    task = inductive_task(
        [], [example(("target(a)", ""), True)], [], [], [], max_program_clauses=1
    )
    space = make_clause_space(["target(a).", "target(b).", "target(c)."])
    proposals = []

    def initialize(context):
        proposals.append(1)
        programs = (
            ["target(b)."]
            if solution_stage == "refill" and len(proposals) == 1
            else ["target(a).", "target(c)."]
        )
        return [context.hypotheses.encode((source,)) for source in programs]

    evaluated = []
    evaluate = CandidateEvaluator.__call__

    def record_evaluation(self, candidate):
        evaluated.append(tuple(str(statement) for statement in candidate))
        return evaluate(self, candidate)

    monkeypatch.setattr(pool_search, "create_population", lambda config: initialize)
    monkeypatch.setattr(CandidateEvaluator, "__call__", record_evaluation)
    result = epoch_pool_genetic_search(_pool_arguments(size=3), task, space)
    assert result.is_solution
    assert result.hypothesis == ("target(a).",)
    assert evaluated == (
        [("target(a).",)]
        if solution_stage == "initialization"
        else [("target(b).",), ("target(a).",)]
    )


def test_epoch_releases_previous_evaluator_before_constructing_next(monkeypatch):
    task, space = _general_pool_task()
    previous = []
    create_evaluator = pool_search.create_epoch_pool_evaluator

    def check_lifetime(*args, **kwargs):
        gc.collect()
        assert all(reference() is None for reference in previous)
        evaluator = create_evaluator(*args, **kwargs)
        previous.append(weakref.ref(evaluator))
        return evaluator

    monkeypatch.setattr(pool_search, "create_epoch_pool_evaluator", check_lifetime)
    epoch_pool_genetic_search(_pool_arguments(), task, space)
    assert len(previous) == 4
