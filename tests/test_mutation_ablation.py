import random

import pytest

from gentians.evolution.context import EvolutionContext
from gentians.evolution.mutations import create_mutation
from gentians.evolution.mutations.random_group import RandomGroupMutation
from gentians.evaluation import create_evaluator
from gentians.hypotheses import HypothesisGenerator
from tests.task_helpers import example, inductive_task, make_clause_space
from tests.test_body_local_mutation import task_and_generator


def test_disabled_guidance_does_not_request_fitness():
    _, h = task_and_generator([":- p.", ":- q."])
    genome = h.encode([":- p."])
    def evaluate(_):
        pytest.fail("Unguided mutation must not evaluate an intermediate child")
    result = RandomGroupMutation(1, completeness_guidance=False)(
        genome, EvolutionContext(h, random.Random(1), evaluate=evaluate))
    assert result.genome != genome


def test_head_preference_is_inert_for_constraint_only_space():
    _, h = task_and_generator([":- p.", ":- q.", ":- r."])
    genome = h.encode([":- p."])
    for seed in range(50):
        outputs = []
        for jump in (0.1, 1.0):
            rng = random.Random(seed)
            result = RandomGroupMutation(1, random_jump_probability=jump)(
                genome, EvolutionContext(h, rng))
            outputs.append((result.genome, rng.getstate()))
        assert outputs[0] == outputs[1]


def test_ablation_can_replace_complete_headed_program_within_limits():
    task = inductive_task(["p.", "q.", "bad."], [example(("goal", ""), True)],
                          [example(("bad", ""), False)], [], [])
    h = HypothesisGenerator(task, make_clause_space(["goal :- p.", "goal :- q."]), 1)
    genome = h.encode(["goal :- p."])
    evaluate = create_evaluator(task, {"scoring": "cov_program"})
    result = evaluate(h.program(genome))
    assert result.is_complete and not result.is_solution
    for guidance in (True, False):
        proposal = RandomGroupMutation(1, complete_generator_removal_probability=0,
                                       completeness_guidance=guidance)(
            genome, EvolutionContext(h, random.Random(1), results={genome: result}))
        assert proposal.genome.bit_count() == 1
        assert (proposal.genome == genome) is guidance
        assert evaluate(h.program(proposal.genome)).is_complete


@pytest.mark.parametrize("value", [0, 1, "false", None])
def test_guidance_requires_boolean(value):
    with pytest.raises(ValueError, match="completeness_guidance"):
        create_mutation({"name": "random_group", "probability": 1,
                         "completeness_guidance": value})
