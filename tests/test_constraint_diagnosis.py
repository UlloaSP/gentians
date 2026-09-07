import random

import pytest

from gentians.evaluation import create_evaluator
from gentians.evolution.context import EvolutionContext
from gentians.evolution.mutations.random_group import RandomGroupMutation
from gentians.hypotheses import HypothesisGenerator
from gentians.language.asp import parse_program
from tests.task_helpers import example, inductive_task, make_clause_space


def test_diagnosis_distinguishes_missing_heads_and_blocked_witnesses():
    task = inductive_task(["{a}."], [example(("p", ""), True)], [], [], [])
    evaluate = create_evaluator(task, {"scoring": "cov_program", "constraint_diagnosis": True})
    blocked = evaluate(parse_program("p :- a. :- a."))
    missing = evaluate(parse_program(":- a."))
    assert not blocked.is_complete and blocked.potential_complete
    assert blocked.potential_pos_mask == 1
    assert not missing.is_complete and not missing.potential_complete
    assert missing.potential_pos_mask == 0
    # Same headed program, different learned constraints: reuse one diagnosis.
    evaluate(parse_program("p :- a. :- p."))
    assert len(evaluate.solver._positive_ceilings) == 2


def test_diagnosis_retains_context_constraints_exclusions_and_strong_negation():
    task = inductive_task(
        ["{a}. -p :- a."],
        [example(("-p", "b", ""), True), example(("-p", "", ":- a."), True)],
        [], [], [],
    )
    evaluate = create_evaluator(task, {"scoring": "cov_program", "constraint_diagnosis": True})
    result = evaluate(parse_program(":- a."))
    assert result.behavior == (0, 0)
    assert result.potential_pos_mask == 1
    assert result.potential_complete is False


@pytest.mark.parametrize("background, clauses, source, potential", [
    (["{a}."], ["p :- a.", ":- a.", ":- not a."], ["p :- a.", ":- a."], True),
    (["a."], ["p :- a.", "q :- a.", ":- p."], ["q :- a.", ":- p."], False),
])
def test_repair_changes_only_diagnosed_role(background, clauses, source, potential):
    task = inductive_task(background, [example(("p", ""), True)],
                          [example(("q", ""), False)], [], [])
    h = HypothesisGenerator(task, make_clause_space(clauses), 3)
    genome = h.encode(tuple(source))
    evaluate = create_evaluator(task, {"scoring": "cov_program", "constraint_diagnosis": True})
    result = evaluate(h.program(genome))
    assert result.potential_complete is potential
    for seed in range(10):
        context = EvolutionContext(h, random.Random(seed), results={genome: result})
        child = RandomGroupMutation(1.0, repair_probability=1.0)(genome, context).genome
        assert child != genome
        changed = child ^ genome
        assert not changed & (~h.constraint_clauses if potential else h.constraint_clauses)


def test_repair_does_not_classify_unknown_constraint_only_inputs():
    task = inductive_task(["{p;q}."], [example(("p", ""), True)],
                          [example(("q", ""), False)], [], [])
    h = HypothesisGenerator(task, make_clause_space([":- p.", ":- q."]), 2)
    context = EvolutionContext(h, random.Random(1), lambda _: pytest.fail("Extra evaluation"))
    RandomGroupMutation(1.0, constraint_only_random=True, repair_probability=1.0)(1, context)


@pytest.mark.parametrize("value", [True, -0.1, 1.1])
def test_repair_probability_validation(value):
    with pytest.raises(ValueError, match="repair_probability"):
        RandomGroupMutation(1.0, repair_probability=value)


def test_diagnosis_repair_obeys_duplicate_retry_budget(monkeypatch):
    from gentians.evaluation.result import EvaluationResult
    from gentians.evolution.operator_types import MutationProposal

    task = inductive_task(["{p;q}."], [example(("p", ""), True)], [], [], [])
    h = HypothesisGenerator(task, make_clause_space([":- p.", ":- q.", ":- not q."]), 3)
    result = EvaluationResult(0, False, (0, 0), False, True, 1, True)
    context = EvolutionContext(h, random.Random(1), results={1: result}, seen={3})
    mutation = RandomGroupMutation(1, repair_probability=1, duplicate_retries=1)
    proposals = iter([MutationProposal(3), MutationProposal(5)])
    monkeypatch.setattr(mutation, "_propose", lambda *args: next(proposals))
    assert mutation(1, context).genome == 5


def test_no_constraints_means_no_inert_repair_rng_draw():
    task = inductive_task(["a."], [example(("p", ""), True)], [], [], [])
    h = HypothesisGenerator(task, make_clause_space(["p :- a.", "q :- a."]), 2)
    genome = h.encode(("q :- a.",))
    result = create_evaluator(task, {"scoring": "cov_program", "constraint_diagnosis": True})(h.program(genome))
    for seed in range(20):
        first = EvolutionContext(h, random.Random(seed), results={genome: result})
        second = EvolutionContext(h, random.Random(seed), results={genome: result})
        assert RandomGroupMutation(1)(genome, first) == RandomGroupMutation(1, repair_probability=1)(genome, second)
        assert first.rng.getstate() == second.rng.getstate()


def test_semantic_effect_logging_uses_whole_program_masks(monkeypatch):
    from gentians.evaluation.result import EvaluationResult
    from gentians.evolution import metrics
    from gentians.evolution.operator_types import MutationProposal

    rows = []
    monkeypatch.setattr(metrics, "operator_metrics_enabled", lambda: True)
    monkeypatch.setattr(metrics, "record_metric", lambda name, row: rows.append(row))
    before = EvaluationResult(0, False, (3, 5), False, False)
    after = EvaluationResult(0, False, (6, 6), False, False)
    metrics.record_mutation("random_group", 1, MutationProposal(2), duplicate=False,
                            before=before, after=after)
    assert rows[0]["semantic_effect_known"]
    assert all(rows[0][field] == 1 for field in (
        "positive_recovered", "positive_lost", "negative_removed", "negative_introduced",
    ))


def test_cached_diagnosis_does_not_enable_disabled_legacy_guidance(monkeypatch):
    from gentians.evaluation.result import EvaluationResult
    from gentians.evolution.operator_types import MutationProposal

    task = inductive_task(["a."], [example(("p", ""), True)], [], [], [])
    h = HypothesisGenerator(task, make_clause_space(["p :- a.", "q :- a."]), 2)
    result = EvaluationResult(0, False, (0, 0), False, True, 0, False)
    context = EvolutionContext(h, random.Random(1), results={1: result})
    mutation = RandomGroupMutation(1, completeness_guidance=False, repair_probability=1)
    observed = []

    def propose(genome, context, classification, remove_headed):
        observed.append(classification)
        return MutationProposal(genome)

    monkeypatch.setattr(mutation, "_propose", propose)
    mutation(1, context)
    assert observed == [None]
