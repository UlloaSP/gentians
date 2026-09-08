import random

import pytest

from gentians.algorithms.pool_policy import (
    build_clause_pool,
    retain_population,
)
from gentians.evolution.individual import Individual
from gentians.evolution.reproduction import ReproductiveHistory
from gentians.hypotheses import HypothesisGenerator
from tests.task_helpers import inductive_task, make_clause_space


@pytest.mark.parametrize("policy", ["fitness", "behavior", "reproductive"])
def test_retention_preserves_champion_and_exact_size(policy):
    champion = Individual(1, 10, False, (1, 0))
    population = [Individual(2, 8, False), Individual(4, 7, False)]
    retained = retain_population(population, champion, 2, policy, ReproductiveHistory())
    assert champion in retained
    assert len(retained) == 2
    assert len({item.genome for item in retained}) == 2


def test_diversity_retains_positive_specialist_and_negative_avoidance():
    champion = Individual(1, 10, False, (1, 3))
    redundant = Individual(2, 9, False, (1, 3))
    specialist = Individual(4, 3, False, (2, 3))
    consistent = Individual(8, 2, False, (1, 0))
    retained = retain_population(
        [champion, redundant, specialist, consistent], champion, 3, "behavior", None
    )
    assert retained == [champion, consistent, specialist]


def test_reproductive_retention_balances_specialists_success_and_exploration():
    champion = Individual(1, 10, False, (1, 0))
    specialist = Individual(2, 2, False, (2, 0))
    productive = Individual(4, 3, False, (1, 0))
    untried = Individual(8, 4, False, (1, 0))
    unsuccessful = Individual(16, 9, False, (1, 0))
    history = ReproductiveHistory()
    history.observe(productive, productive, champion)
    history.observe(unsuccessful, unsuccessful, None)
    retained = retain_population(
        [champion, specialist, productive, untried, unsuccessful],
        champion,
        4,
        "reproductive",
        history,
    )
    assert retained == [champion, specialist, productive, untried]


@pytest.mark.parametrize("policy", ["random", "neighbors"])
def test_pool_build_preserves_seeds_and_closes_sampled_candidates(policy):
    task = inductive_task(["seed(a)."], [], [], [], [])
    space = make_clause_space(
        ["p(X) :- seed(X).", "q(X) :- p(X).", "r(X) :- q(X).", "s(a)."]
    )
    hypotheses = HypothesisGenerator(task, space, max_clauses=3)
    seed = hypotheses.encode(("p(X) :- seed(X).", "q(X) :- p(X)."))
    pool = build_clause_pool(hypotheses, [seed], 3, policy, random.Random(4))
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
    hypotheses.set_pool(pool)
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
