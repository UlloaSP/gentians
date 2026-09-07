import random

import pytest

from gentians.evaluation.result import EvaluationResult
from gentians.evolution.context import EvolutionContext
from gentians.evolution.individual import Individual
from gentians.evolution.mutations import create_mutation
from gentians.evolution.mutations.random_group import RandomGroupMutation
from gentians.evolution.operator_types import MutationProposal
from gentians.evolution.replacements import create_replacement
from gentians.evolution.replacements.oldest_or_worst import OldestOrWorstReplacement
from tests.test_block_mutation import generator


def individual(genome, score, complete=False):
    return Individual(genome, score, False, is_complete=complete)


def test_retry_uses_admission_history_not_classification_cache(monkeypatch):
    h = generator(["goal.", "bad.", "other."])
    mutation = RandomGroupMutation(1, duplicate_retries=3)
    attempts = []
    def propose(genome, context, result, remove_headed):
        attempts.append(genome)
        return MutationProposal(2 if len(attempts) == 1 else 4)
    monkeypatch.setattr(mutation, "_propose", propose)
    classified = {4: EvaluationResult(0, False, (0, 0), False, True)}
    result = mutation(1, EvolutionContext(h, random.Random(1), results=classified, seen={2}))
    assert result.genome == 4
    assert attempts == [1, 1]


@pytest.mark.parametrize("retries", [0, 3])
def test_duplicate_retries_are_bounded_and_do_not_evaluate(monkeypatch, retries):
    h = generator(["goal."])
    mutation = RandomGroupMutation(1, duplicate_retries=retries)
    calls = []
    def propose(genome, context, result, remove_headed):
        calls.append(genome)
        return MutationProposal(genome)
    monkeypatch.setattr(mutation, "_propose", propose)
    context = EvolutionContext(h, random.Random(1), seen={1})
    assert mutation(1, context).genome == 1
    assert len(calls) == 1 + retries


def test_retry_gate_and_known_solutions_remain_protected(monkeypatch):
    h = generator(["goal."])
    complete = EvaluationResult(1, True, (1, 0), True, True)
    context = EvolutionContext(h, random.Random(1), results={1: complete}, seen={1})
    assert RandomGroupMutation(1, duplicate_retries=3)(1, context).skipped
    mutation = RandomGroupMutation(0, duplicate_retries=3)
    monkeypatch.setattr(mutation, "_propose", lambda *args: pytest.fail("Gate was bypassed"))
    assert mutation(1, context).skipped


def test_retries_do_not_redraw_complete_generator_escape(monkeypatch):
    h = generator(["goal.", "bad."])
    before = h.all_clauses
    result = EvaluationResult(0, False, (1, 1), True, False)
    rng = random.Random(1)
    draws = []
    def draw():
        draws.append(0.5)
        return 0.5
    monkeypatch.setattr(rng, "random", draw)
    mutation = RandomGroupMutation(1, duplicate_retries=3)
    attempts = []
    def propose(genome, context, result, remove_headed):
        attempts.append(remove_headed)
        return MutationProposal(genome)
    monkeypatch.setattr(mutation, "_propose", propose)
    mutation(before, EvolutionContext(h, rng, results={before: result}, seen={before}))
    assert draws == [0.5, 0.5]
    assert attempts == [False] * 4


def test_complete_reserve_accepts_lower_fitness_without_losing_best():
    population = [individual(1, 10), individual(2, 9), individual(4, 8)]
    candidate = individual(8, 1, True)
    updated = OldestOrWorstReplacement(0, 1)(population, candidate, random.Random(1))
    assert [x.genome for x in updated] == [1, 2, 8]
    assert [x.genome for x in population] == [1, 2, 4]
    # An incomplete candidate cannot evict the reserved complete individual.
    assert OldestOrWorstReplacement(0, 1)(updated, individual(16, 5), random.Random(1)) is updated
    improved = OldestOrWorstReplacement(0, 1)(updated, individual(16, 2, True), random.Random(1))
    assert [x.genome for x in improved] == [1, 2, 16]


def test_reserve_is_capped_and_does_not_invent_complete_candidates():
    population = [individual(1, 10), individual(2, 9), individual(4, 8)]
    strategy = OldestOrWorstReplacement(1, 100)
    updated = strategy(population, individual(8, 0, True), random.Random(1))
    updated = strategy(updated, individual(16, -1, True), random.Random(1))
    assert updated[0].genome == 1
    assert sum(x.is_complete for x in updated) == 2
    singleton = [population[0]]
    assert strategy(singleton, individual(8, 0, True), random.Random(1)) is singleton
    assert strategy(population, individual(8, 0), random.Random(1)) is population


@pytest.mark.parametrize("value", [True, -1, 1.5, "3"])
def test_factories_validate_exploration_counts(value):
    with pytest.raises(ValueError):
        create_mutation({"name": "random_group", "probability": 1, "duplicate_retries": value})
    with pytest.raises(ValueError):
        create_replacement({"name": "oldest_or_worst", "prob_replacing_oldest": 0,
                            "complete_quota": value})


def test_exploration_matrix_changes_only_the_two_controls():
    from benchmarks.run_experiments import DEFAULT_CONFIG, load_config

    _, experiments = load_config(DEFAULT_CONFIG)
    entries = {e["id"].split("/")[1]: e for e in experiments
               if e["id"].startswith("directed-exploration/")}
    knobs = {"mutation.duplicate_retries", "replacement.complete_quota"}
    control = entries["control"]["overrides"]
    for name, retries, quota in (("control", 0, 0), ("retries", 3, 0),
                                 ("reserve", 0, 1), ("combined", 3, 1)):
        entry = entries[name]
        assert entry["runs"] == 10 and entry["timeout_seconds"] == 300
        assert entry["overrides"]["iterations_genetic"] == 0
        assert entry["overrides"]["mutation.duplicate_retries"] == retries
        assert entry["overrides"]["replacement.complete_quota"] == quota
        assert {k: v for k, v in entry["overrides"].items() if k not in knobs} == {
            k: v for k, v in control.items() if k not in knobs}
