import random


from gentians.algorithms.incremental_clause_genetic import (
    _activate_clauses,
    retain_population,
)
from gentians.evolution.individual import Individual
from gentians.hypotheses import HypothesisGenerator

import pytest

from gentians import gentians as entrypoint
from gentians.algorithms import incremental_clause_genetic as pool_search
from gentians.algorithms.result import SearchResult
from gentians.arguments import Arguments
from gentians.algorithms.incremental_clause_genetic import incremental_clause_genetic_search
from gentians.evaluation.evaluator import CandidateEvaluator
from tests.task_helpers import example, inductive_task, make_clause_space




@pytest.mark.parametrize("algorithm", ["steady_state", "incremental"])
def test_solve_selects_configured_search(monkeypatch, algorithm):
    calls = []
    result = SearchResult(("target(a).",), 1.0, True)
    monkeypatch.setattr(
        entrypoint,
        "steady_state_genetic_search",
        lambda *args: calls.append("steady") or result,
    )
    monkeypatch.setattr(
        entrypoint,
        "incremental_clause_genetic_search",
        lambda *args: calls.append("pool") or result,
    )
    arguments = Arguments()
    arguments.algorithm = algorithm

    entrypoint.solve(inductive_task([], [], [], [], []), arguments)

    assert calls == ["pool" if algorithm == "incremental" else "steady"]


@pytest.mark.parametrize(
    "config",
    [
        {"batch_size": 0, "epoch_generations": 1, "elite_count": 1},
        {"batch_size": 1, "epoch_generations": True, "elite_count": 1},
        {"batch_size": 1, "epoch_generations": 1, "elite_count": 4},
    ],
)
def test_incremental_search_rejects_invalid_config(config):
    arguments = Arguments(
        evaluation={"scoring": "cov_program", "constraint_inheritance": False},
        iterations_genetic=1,
        population={"name": "random", "size": 3},
        incremental=config,
    )

    with pytest.raises(ValueError, match="incremental"):
        incremental_clause_genetic_search(
            arguments,
            inductive_task([], [], [], [], []),
            make_clause_space(["target(a)."]),
        )




def _incremental_arguments(**overrides):
    return Arguments(
        evaluation={"scoring": "cov_program", "constraint_inheritance": False},
        iterations_genetic=8,
        random_seed=17,
        population={"name": "random", "size": 4},
        incremental={
            "batch_size": 4,
            "epoch_generations": 2,
            "elite_count": 2,
            **overrides,
        },
    )








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
    result = incremental_clause_genetic_search(_incremental_arguments(batch_size=3), task, space)
    assert result.is_solution
    assert result.hypothesis == ("target(a).",)
    assert evaluated == (
        [("target(a).",)]
        if solution_stage == "initialization"
        else [("target(b).",), ("target(a).",)]
    )

def test_retention_preserves_champion_and_exact_size():
    champion = Individual(1, 10, False, (1, 0))
    population = [Individual(2, 8, False), Individual(4, 7, False)]
    retained = retain_population(population, champion, 2)
    assert champion in retained
    assert len(retained) == 2
    assert len({item.genome for item in retained}) == 2






def test_pool_build_preserves_seeds_and_closes_sampled_candidates():
    task = inductive_task(["seed(a)."], [], [], [], [])
    space = make_clause_space(
        ["p(X) :- seed(X).", "q(X) :- p(X).", "r(X) :- q(X).", "s(a)."]
    )
    hypotheses = HypothesisGenerator(task, space, max_clauses=3)
    seed = hypotheses.encode(("p(X) :- seed(X).", "q(X) :- p(X)."))
    pool = _activate_clauses(hypotheses, [seed], 3, random.Random(4))
    assert pool & seed == seed
    assert pool == hypotheses.available_clauses
    assert pool.bit_count() >= 3
    for number in range(30):
        candidate = hypotheses.create(random.Random(number))
        if candidate is None:
            continue
        assert candidate & ~pool == 0
        assert candidate.bit_count() <= 3
        selected = [
            entry
            for index, entry in enumerate(hypotheses.space.entries)
            if candidate & (1 << index)
        ]
        heads = {head for entry in selected for head in entry.heads}
        deps = {dependency for entry in selected for dependency in entry.deps}
        assert deps <= heads | {("seed", 1)}


def test_restricted_sampler_preserves_ascending_rank_rng_sequence():
    hypotheses = HypothesisGenerator(
        inductive_task([], [], [], [], []),
        make_clause_space([f"p({index})." for index in range(12)]),
        max_clauses=4,
    )
    pool = sum(1 << index for index in (0, 2, 5, 6, 9, 11))
    hypotheses.set_available_clauses(pool)
    excluded = (1 << 2) | (1 << 9)
    for seed in range(30):
        actual_rng = random.Random(seed)
        reference_rng = random.Random(seed)
        remaining = pool & ~excluded
        expected = []
        while remaining:
            ids = [index for index in range(12) if remaining & (1 << index)]
            selected = ids[reference_rng.randrange(len(ids))]
            expected.append(selected)
            remaining &= ~(1 << selected)
        assert list(hypotheses._random_available(excluded, actual_rng)) == expected
        assert actual_rng.getstate() == reference_rng.getstate()
