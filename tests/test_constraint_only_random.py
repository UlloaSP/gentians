import random

import pytest

from gentians.evolution.context import EvolutionContext
from gentians.evolution.mutations.random_group import RandomGroupMutation
from gentians.evaluation import create_evaluator
from gentians.hypotheses import HypothesisGenerator
from tests.task_helpers import example, inductive_task, make_clause_space


def setup(max_clauses):
    task = inductive_task(["p.", "bad.", "{q}."], [example(("p", ""), True)],
                          [example(("bad", ""), False)], [], [])
    h = HypothesisGenerator(task, make_clause_space([":- p.", ":- q."]), max_clauses)
    return h, create_evaluator(task, {"scoring": "cov_program"})


def test_constraint_policy_can_append_without_intermediate_fitness(monkeypatch):
    h, evaluate = setup(2)
    before = h.encode([":- p."])
    assert not evaluate(h.program(before)).is_complete
    rng = random.Random(1)
    monkeypatch.setattr(rng, "shuffle", lambda values: values.sort(key=lambda v: v != "append"))
    def classify(_):
        pytest.fail("Unrestricted constraint policy must not classify intermediate input")
    after = RandomGroupMutation(1)(
        before, EvolutionContext(h, rng, evaluate=classify))
    assert after.operation == "append"
    assert after.genome.bit_count() == 2




def test_constraint_policy_never_introduces_constraints_without_negatives():
    task = inductive_task(["p.", "q.", "r."], [example(("p", ""), True)], [], [], [])
    h = HypothesisGenerator(task, make_clause_space([":- p.", ":- q.", ":- r."]), 3)
    before = h.encode([":- p.", ":- q."])
    for seed in range(30):
        after = RandomGroupMutation(1)(before, EvolutionContext(h, random.Random(seed)))
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


def test_cached_perfect_constraint_program_still_skips_mutation():
    task = inductive_task(["p.", "{q}."], [example(("p", ""), True)],
                          [example(("q", ""), False)], [], [])
    h = HypothesisGenerator(task, make_clause_space([":- p.", ":- q."]), 1)
    before = h.encode([":- q."])
    result = create_evaluator(task, {"scoring": "cov_program"})(h.program(before))
    assert result.is_solution
    after = RandomGroupMutation(1)(
        before, EvolutionContext(h, random.Random(1), results={before: result}))
    assert after.skipped and after.genome == before




def test_head_preference_is_inert_for_constraint_only_space():
    h, _ = setup(2)
    genome = h.encode([":- p."])
    for seed in range(50):
        outputs = []
        for jump in (0.1, 1.0):
            rng = random.Random(seed)
            result = RandomGroupMutation(1, random_jump_probability=jump)(
                genome, EvolutionContext(h, rng))
            outputs.append((result.genome, rng.getstate()))
        assert outputs[0] == outputs[1]
