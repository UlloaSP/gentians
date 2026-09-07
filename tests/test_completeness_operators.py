import random

import pytest

from gentians.evaluation import create_evaluator
from gentians.evaluation.result import EvaluationResult
from gentians.evolution.context import EvolutionContext
from gentians.evolution.crossovers import create_crossover
from gentians.evolution.mutations import create_mutation
from gentians.evolution.crossovers.set_mix import SetMixCrossover
from gentians.evolution.mutations.random_group import RandomGroupMutation
from gentians.hypotheses import HypothesisGenerator
from tests.task_helpers import example, inductive_task, make_clause_space


def prepared():
    task = inductive_task(["q."], [example(("p", ""), True)],
                          [example(("r", ""), False)], [], [], max_program_clauses=4)
    space = make_clause_space(["p.", "r.", ":- p, q.", ":- r, q."])
    return task, HypothesisGenerator(task, space, 4)


@pytest.mark.parametrize("operation", ["append", "remove", "replace"])
def test_constraint_mutation_preserves_heads_and_cannot_add_providers(operation):
    _, hypotheses = prepared()
    genome = hypotheses.encode(["p.", ":- p, q."])
    for seed in range(10):
        candidate = getattr(hypotheses, operation)(
            genome, random.Random(seed), mutable=hypotheses.constraint_clauses)
        if candidate is not None:
            assert candidate & ~hypotheses.constraint_clauses == genome & ~hypotheses.constraint_clauses
            assert "r." not in hypotheses.render(candidate)
            assert ":- r, q." not in hypotheses.render(candidate)


def test_complete_parent_heads_survive_crossover():
    _, hypotheses = prepared()
    first = hypotheses.encode(["p.", ":- p, q."])
    second = hypotheses.encode(["r.", ":- r, q."])
    for seed in range(10):
        child = hypotheses.mix_constraints(first, second, (0.7, 0.3), random.Random(seed))
        assert child is not None
        assert child & ~hypotheses.constraint_clauses == first & ~hypotheses.constraint_clauses


def test_mutation_classifies_its_actual_input_and_preserves_solution():
    _, hypotheses = prepared()
    genome = hypotheses.encode(["p."])
    calls = []

    def evaluate(candidate):
        calls.append(candidate)
        return EvaluationResult(100, True, (1, 0), True, True)

    context = EvolutionContext(hypotheses, random.Random(1), evaluate)
    proposal = RandomGroupMutation(1.0)(genome, context)
    assert calls == [genome]
    assert proposal.genome == genome
    assert proposal.skipped


def test_constraint_changes_can_destroy_completeness():
    task = inductive_task([], [example(("p", ""), True)],
                          [example(("p", ""), False)], [], [],
                          max_program_clauses=2)
    hypotheses = HypothesisGenerator(task, make_clause_space(["p.", ":- p."]), 2)
    evaluate = create_evaluator(task, {"scoring": "cov_program"})
    before = hypotheses.encode(["p."])
    after = hypotheses.append(before, random.Random(1), mutable=hypotheses.constraint_clauses)
    assert after is not None
    assert evaluate(hypotheses.program(before)).is_complete
    assert not evaluate(hypotheses.program(after)).is_complete


@pytest.mark.parametrize("complete,consistent", [(False, True), (True, False)])
def test_no_examples_do_not_freeze_headed_space(complete, consistent):
    task = inductive_task([], [], [], [], [], max_program_clauses=1)
    hypotheses = HypothesisGenerator(task, make_clause_space(["p.", "r."]), 1)
    genome = hypotheses.encode(["p."])

    def evaluate(_candidate):
        return EvaluationResult(0, False, (0, 0), complete, consistent)

    context = EvolutionContext(hypotheses, random.Random(2), evaluate)
    proposal = RandomGroupMutation(1.0, random_jump_probability=1.0)(genome, context)
    assert hypotheses.render(proposal.genome) == ("r.",)


@pytest.mark.parametrize("strategy", ["random_group"])
def test_incomplete_constraint_only_program_can_recover_positive(strategy):
    task = inductive_task(["{p}.", "q."], [example(("p", ""), True)],
                          [example(("q", ""), False)], [], [], max_program_clauses=2)
    h = HypothesisGenerator(task, make_clause_space([":- p.", ":- not q."]), 2)
    genome = h.all_clauses
    evaluator = create_evaluator(task, {"scoring": "cov_program"})
    assert not evaluator(h.program(genome)).is_complete
    mutation = create_mutation({"name": strategy, "probability": 1.0})
    children = [mutation(genome, EvolutionContext(h, random.Random(seed))).genome
                for seed in range(10)]
    assert any(evaluator(h.program(child)).is_complete for child in children)


@pytest.mark.parametrize("operation", ["append", "remove", "replace", "mix", "create"])
def test_positive_only_programs_drop_optional_constraints(operation):
    # Exclusions inside positive examples still have existential semantics.
    task = inductive_task(["{q}."], [example(("p", "q"), True)], [], [], [],
                          max_program_clauses=3)
    h = HypothesisGenerator(task, make_clause_space(["p.", "r.", ":- q."]), 3)
    genome = h.encode(["p.", ":- q."])
    rng = random.Random(1)
    if operation == "mix":
        child = h.mix(genome, h.encode(["r."]), (1.0, 1.0), rng)
    elif operation == "create":
        child = h.create(rng)
    else:
        child = getattr(h, operation)(genome, rng)
    if child is not None and child & ~h.constraint_clauses:
        assert not child & h.constraint_clauses


@pytest.mark.parametrize("strategy", ["random_group"])
def test_complete_but_inseparable_program_can_change_heads(strategy):
    task = inductive_task([], [example(("p", ""), True)],
                          [example(("q", ""), False)], [], [], max_program_clauses=3)
    h = HypothesisGenerator(task, make_clause_space(["p.", "q.", ":- q."]), 3)
    genome = h.encode(["p.", "q."])
    evaluator = create_evaluator(task, {"scoring": "cov_program"})
    def evaluate(candidate):
        return evaluator(h.program(candidate))
    assert evaluate(genome).is_complete and not evaluate(genome).is_solution
    mutation = create_mutation({"name": strategy, "probability": 1.0})
    children = [mutation(genome, EvolutionContext(h, random.Random(seed), evaluate)).genome
                for seed in range(100)]
    assert any(evaluate(child).is_solution for child in children)


def test_complete_crossover_prefers_recipient_heads_but_can_escape():
    _, h = prepared()
    first = h.encode(["p.", ":- p, q."])
    second = h.encode(["r.", ":- r, q."])
    results = {g: EvaluationResult(0, False, (0, 0), g == first, False)
               for g in (first, second)}
    children = [SetMixCrossover(1.0)(second, first,
                EvolutionContext(h, random.Random(seed), results=results))
                for seed in range(100)]
    heads = first & ~h.constraint_clauses
    assert any(c is not None and c != first and c & ~h.constraint_clauses == heads
               for c in children)
    assert any(c is not None and c & ~h.constraint_clauses != heads for c in children)


def test_homogeneous_mutation_classifies_but_crossover_keeps_lazy_path():
    task = inductive_task(["{p;q}."], [example(("p", ""), True)],
                          [example(("q", ""), False)], [], [])
    h = HypothesisGenerator(task, make_clause_space([":- p.", ":- q."]), 2)
    calls = []
    def evaluate(genome):
        calls.append(genome)
        return EvaluationResult(0, False, (0, 0), False, True)
    context = EvolutionContext(h, random.Random(1), evaluate)
    RandomGroupMutation(1.0)(h.all_clauses, context)
    SetMixCrossover(1.0)(1, 2, context)
    assert calls == [h.all_clauses]


def test_removed_completeness_strategy_names_fail_explicitly():
    for factory in (create_mutation, create_crossover):
        with pytest.raises(ValueError, match="Unknown"):
            factory({"name": "completeness", "probability": 1.0})


@pytest.mark.parametrize("strategy", ["random_group"])
def test_cached_solution_is_preserved_even_in_homogeneous_space(strategy):
    task = inductive_task([], [example(("p", ""), True)], [], [], [])
    h = HypothesisGenerator(task, make_clause_space(["p.", "q."]), 2)
    genome = h.encode(["p."])
    results = {genome: EvaluationResult(100, True, (1, 0), True, True)}
    context = EvolutionContext(h, random.Random(1), results=results)
    proposal = create_mutation({"name": strategy, "probability": 1.0})(genome, context)
    assert proposal.genome == genome and proposal.skipped
    assert SetMixCrossover(1.0)(genome, h.encode(["q."]), context) == genome


def test_no_positive_examples_do_not_freeze_headed_rules():
    task = inductive_task([], [], [example(("p", ""), False)], [], [],
                          max_program_clauses=1)
    h = HypothesisGenerator(task, make_clause_space(["p.", "q.", ":- p."]), 1)
    genome = h.encode(["p."])
    results = {genome: EvaluationResult(0, False, (0, 1), True, False)}
    child = RandomGroupMutation(1.0, random_jump_probability=1.0)(
        genome, EvolutionContext(h, random.Random(1), results=results))
    assert h.render(child.genome) == ("q.",)


def test_mixed_mutation_evaluates_actual_child_and_reuses_cache():
    task = inductive_task(["q."], [example(("p", ""), True)],
                          [example(("q", ""), False)], [], [], max_program_clauses=2)
    h = HypothesisGenerator(task, make_clause_space(["p.", ":- p."]), 2)
    evaluator = create_evaluator(task, {"scoring": "cov_program"})
    parent = h.encode(["p."])
    crossed = h.all_clauses
    results = {parent: evaluator(h.program(parent))}
    calls = []

    def evaluate(genome):
        calls.append(genome)
        results[genome] = evaluator(h.program(genome))
        return results[genome]

    context = EvolutionContext(h, random.Random(1), evaluate, results)
    mutation = RandomGroupMutation(1.0)
    mutation(crossed, context)
    mutation(crossed, context)
    assert calls == [crossed]
    assert results[parent].is_complete
    assert not results[crossed].is_complete


@pytest.mark.parametrize("operation", ["append", "replace"])
def test_homogeneous_constraint_sampling_matches_unrestricted_rng(operation):
    task = inductive_task(["{p;q;r}."], [], [example(("p", ""), False)], [], [])
    space = make_clause_space([":- p.", ":- q.", ":- r."])
    for seed in range(10):
        unrestricted = HypothesisGenerator(task, space, 3)
        restricted = HypothesisGenerator(task, space, 3)
        first_rng, second_rng = random.Random(seed), random.Random(seed)
        first = getattr(unrestricted, operation)(1, first_rng)
        second = getattr(restricted, operation)(1, second_rng, mutable=restricted.constraint_clauses)
        assert first == second
        assert first_rng.getstate() == second_rng.getstate()


def test_crossover_child_is_classified_after_losing_parent_completeness():
    task = inductive_task(["{p;q}."], [example(("p", ""), True)],
                          [example(("r", ""), False)], [], [], max_program_clauses=3)
    h = HypothesisGenerator(task, make_clause_space(
        ["r.", ":- p, q.", ":- p, not q."]), 3)
    first = h.encode(["r.", ":- p, q."])
    second = h.encode(["r.", ":- p, not q."])
    evaluator = create_evaluator(task, {"scoring": "cov_program"})
    results = {g: evaluator(h.program(g)) for g in (first, second)}
    assert all(result.is_complete and not result.is_solution for result in results.values())
    calls = []

    def evaluate(genome):
        calls.append(genome)
        results[genome] = evaluator(h.program(genome))
        return results[genome]

    crossover = SetMixCrossover(1.0)
    for seed in range(50):
        context = EvolutionContext(h, random.Random(seed), evaluate, results)
        crossed = crossover(first, second, context)
        if crossed is not None and not evaluator(h.program(crossed)).is_complete:
            assert calls == []
            RandomGroupMutation(1.0)(crossed, context)
            assert calls == [crossed]
            assert not results[crossed].is_complete
            break
    else:
        pytest.fail("no over-pruned child produced by the seeded crossovers")
