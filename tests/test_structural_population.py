import random

import pytest

from gentians.evolution.context import EvolutionContext
from gentians.evolution.populations import create_population
from gentians.evolution.populations.random_population import RandomPopulation
from gentians.hypotheses import HypothesisGenerator
from tests.task_helpers import example, inductive_task, make_clause_space


def test_structural_population_balances_actual_sizes_then_distance(monkeypatch):
    monkeypatch.setattr(RandomPopulation, "__call__", lambda self, context: [3, 5, 12, 1, 7])
    strategy = create_population({"name": "structural_diverse", "size": 4})
    # First sampled candidate, new sizes first, then disjoint size-two program.
    assert strategy(None) == [3, 1, 7, 12]


def test_structural_population_is_valid_reproducible_and_does_not_evaluate():
    task = inductive_task(["a."], [example(("p", ""), True)], [], [], [])
    h = HypothesisGenerator(task, make_clause_space([
        "p :- q.", "q :- a.", "p :- a.", "r :- a.",
    ]), 3)
    strategy = create_population({"name": "structural_diverse", "size": 4})
    def context():
        return EvolutionContext(h, random.Random(12), lambda _: pytest.fail("Extra evaluation"))
    result = strategy(context())
    assert result == strategy(context())
    assert len(result) == len(set(result)) == 4
    consumer, provider = h.encode(("p :- q.",)), h.encode(("q :- a.",))
    for genome in result:
        assert 0 < genome.bit_count() <= 3
        assert not genome & ~h.available_clauses
        assert not genome & consumer or genome & provider


def test_structural_population_stops_when_space_is_too_small():
    task = inductive_task(["a."], [example(("p", ""), True)], [], [], [])
    h = HypothesisGenerator(task, make_clause_space(["p :- a."]), 1)
    result = create_population({"name": "structural_diverse", "size": 10})(
        EvolutionContext(h, random.Random(1)))
    assert result == [1]


def test_structural_population_respects_active_clause_pool():
    task = inductive_task(["a."], [example(("p", ""), True)], [], [], [])
    h = HypothesisGenerator(task, make_clause_space(["p :- a.", "q :- a.", "r :- a."]), 2)
    allowed = h.encode(("p :- a.", "q :- a."))
    h.set_pool(allowed)
    result = create_population({"name": "structural_diverse", "size": 10})(
        EvolutionContext(h, random.Random(8)))
    assert len(result) == 3
    assert all(not genome & ~allowed for genome in result)


@pytest.mark.parametrize("size", [0, -1, True, 1.5])
def test_structural_population_validates_size(size):
    with pytest.raises(ValueError, match="population size"):
        create_population({"name": "structural_diverse", "size": size})
