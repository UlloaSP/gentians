import random

import pytest

from gentians.evolution.context import EvolutionContext
from gentians.evolution.mutations import create_mutation
from gentians.evolution.mutations.random_group import RandomGroupMutation
from gentians.evaluation import create_evaluator
from gentians.hypotheses import HypothesisGenerator
from tests.task_helpers import example, inductive_task, make_clause_space
from tests.test_block_mutation import generator


def setup(max_clauses):
    task = inductive_task(["p.", "bad.", "{q}."], [example(("p", ""), True)],
                          [example(("bad", ""), False)], [], [])
    h = HypothesisGenerator(task, make_clause_space([":- p.", ":- q."]), max_clauses)
    return h, create_evaluator(task, {"scoring": "cov_program"})


def test_opt_in_can_append_constraint_without_intermediate_fitness(monkeypatch):
    h, evaluate = setup(2)
    before = h.encode([":- p."])
    assert not evaluate(h.program(before)).is_complete
    rng = random.Random(1)
    monkeypatch.setattr(rng, "shuffle", lambda values: values.sort(key=lambda v: v != "append"))
    def classify(_):
        pytest.fail("Unrestricted constraint policy must not classify intermediate input")
    after = RandomGroupMutation(1, constraint_only_random=True)(
        before, EvolutionContext(h, rng, evaluate=classify))
    assert after.operation == "append"
    assert after.genome.bit_count() == 2


def test_constraint_only_option_does_not_change_headed_pool_search():
    for seed in range(30):
        outcomes = []
        for enabled in (False, True):
            h = generator(["goal.", "helper.", "goal :- helper.", ":- goal."])
            before = h.encode(["goal."])
            rng = random.Random(seed)
            after = RandomGroupMutation(1, constraint_only_random=enabled)(before, EvolutionContext(h, rng))
            outcomes.append((after, rng.getstate()))
        assert outcomes[0] == outcomes[1]


def test_constraint_only_option_never_introduces_constraints_without_negatives():
    task = inductive_task(["p.", "q.", "r."], [example(("p", ""), True)], [], [], [])
    h = HypothesisGenerator(task, make_clause_space([":- p.", ":- q.", ":- r."]), 3)
    before = h.encode([":- p.", ":- q."])
    for seed in range(30):
        after = RandomGroupMutation(1, constraint_only_random=True)(before, EvolutionContext(h, random.Random(seed)))
        assert after.genome and not after.genome & ~before


def test_constraint_addition_can_improve_fitness_without_recovering_positives():
    task = inductive_task(["{p; r; bad}."],
                          [example(("p", ""), True), example(("r", ""), True)],
                          [example(("bad", ""), False)], [], [])
    h = HypothesisGenerator(task, make_clause_space([":- p.", ":- bad."]), 2)
    evaluate = create_evaluator(task, {"scoring": "cov_program"})
    before = evaluate(h.program(h.encode([":- p."])))
    after = evaluate(h.program(h.all_clauses))
    assert not before.is_complete and not after.is_complete
    assert before.behavior[0] == after.behavior[0]
    assert before.behavior[1] and not after.behavior[1]
    assert after.score > before.score


@pytest.mark.parametrize("constraint_only_random", [False, True])
def test_cached_perfect_constraint_program_still_skips_mutation(constraint_only_random):
    task = inductive_task(["p.", "{q}."], [example(("p", ""), True)],
                          [example(("q", ""), False)], [], [])
    h = HypothesisGenerator(task, make_clause_space([":- p.", ":- q."]), 1)
    before = h.encode([":- q."])
    result = create_evaluator(task, {"scoring": "cov_program"})(h.program(before))
    assert result.is_solution
    after = RandomGroupMutation(1, constraint_only_random=constraint_only_random)(
        before, EvolutionContext(h, random.Random(1), results={before: result}))
    assert after.skipped and after.genome == before


@pytest.mark.parametrize("value", [0, 1, "true", None])
def test_constraint_only_option_requires_boolean(value):
    with pytest.raises(ValueError, match="constraint_only_random"):
        create_mutation({"name": "random_group", "probability": 1, "constraint_only_random": value})
