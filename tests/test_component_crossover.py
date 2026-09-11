import random
from itertools import combinations
from pathlib import Path

import pytest

from gentians.evaluation import create_evaluator
from gentians.evaluation.result import EvaluationResult
from gentians.evolution.context import EvolutionContext
from gentians.evolution.crossovers import create_crossover
from gentians.hypotheses import HypothesisGenerator
from gentians.language import parse_file
from tests.task_helpers import example, inductive_task, make_clause_space


def generator(rules, *, background=(), limit=5, negatives=True):
    task = inductive_task(
        list(background), [example(("goal", ""), True)],
        [example(("bad", ""), False)] if negatives else [], [], [],
    )
    return HypothesisGenerator(task, make_clause_space(rules), limit)


def component_child(h, first, second, rng):
    child = create_crossover({"name": "component_mix", "probability": 1.0})(
        first, second, EvolutionContext(h, rng)
    )
    assert child is not None
    return child


def test_components_inherit_whole_parent_versions_without_repair_or_evaluation(monkeypatch):
    h = generator([
        "p :- q.", "q :- a.", "q :- b.", "q.",
        "r :- s.", "s :- c.", "s :- d.", "keep.",
    ], background=["a.", "b.", "c.", "d."])
    first = h.encode(["p :- q.", "q :- a.", "r :- s.", "s :- c.", "keep."])
    second = h.encode(["p :- q.", "q :- b.", "r :- s.", "s :- d.", "keep."])
    h.set_available_clauses(first | second)

    def unexpected(*_args, **_kwargs):
        pytest.fail("Component crossover must not repair or evaluate")

    monkeypatch.setattr(h, "_complete", unexpected)
    monkeypatch.setattr(h, "_build", unexpected)
    monkeypatch.setattr("clingo.Control", unexpected)
    closure_calls = []
    monkeypatch.setattr(
        "gentians.hypotheses.generator.add",
        lambda name, seconds: closure_calls.append((name, seconds)),
    )
    crossover = create_crossover({"name": "component_mix", "probability": 1.0})
    results = {g: EvaluationResult(0, False, (1, 1), True, False) for g in (first, second)}
    children = set()
    for seed in range(32):
        context = EvolutionContext(h, random.Random(seed), unexpected, results)
        child = crossover(first, second, context)
        assert child is not None
        assert not child & ~(first | second)
        assert child & (first & second) == first & second
        children.add(h.render(child))
    assert children == {
        tuple(sorted(["p :- q.", q, "r :- s.", s, "keep."]))
        for q in ("q :- a.", "q :- b.")
        for s in ("s :- c.", "s :- d.")
    }
    # Missing cached classifications must not cause a fallback evaluation either.
    crossover(first, second, EvolutionContext(h, random.Random(1), unexpected))
    assert closure_calls == []


def test_component_choices_respect_budget_with_unequal_parent_versions():
    h = generator([
        "goal :- p.", "p.", "p :- q.", "q :- r.", "r.",
        "result :- s.", "s.", "s :- t.", "t :- u.", "u.",
    ], limit=6)
    first = h.encode(["goal :- p.", "p.", "result :- s.", "s :- t.", "t :- u.", "u."])
    second = h.encode(["goal :- p.", "p :- q.", "q :- r.", "r.", "result :- s.", "s."])
    short = h.encode(["goal :- p.", "p.", "result :- s.", "s."])
    children = {component_child(h, first, second, random.Random(seed)) for seed in range(32)}
    assert children == {first, second, short}


@pytest.mark.parametrize("limit", [2, 3])
def test_component_union_combines_complementary_grandparent_providers(monkeypatch, limit):
    task = parse_file(Path(__file__).parents[1] / "benchmarks/gentians/grandparent.txt")
    root = "target(V0,V1) :- target_1(V0,V2),target_1(V2,V1)."
    father = "target_1(V0,V1) :- father(V0,V1)."
    mother = "target_1(V0,V1) :- mother(V0,V1)."
    h = HypothesisGenerator(task, make_clause_space([root, father, mother]), limit)
    first, second = h.encode([root, father]), h.encode([root, mother])
    evaluate = create_evaluator(task, {"scoring": "cov_program"}, space=h.space)
    assert not evaluate(h.program(first)).is_solution
    assert not evaluate(h.program(second)).is_solution
    assert evaluate(h.program(first | second)).is_solution

    def unexpected(*_args, **_kwargs):
        pytest.fail("Component union must not repair or evaluate")

    monkeypatch.setattr(h, "_complete", unexpected)
    monkeypatch.setattr(h, "_build", unexpected)
    monkeypatch.setattr("clingo.Control", unexpected)
    children = {component_child(h, first, second, random.Random(seed)) for seed in range(32)}
    assert children == ({first, second, first | second} if limit == 3 else {first, second})


@pytest.mark.parametrize("seed, expected, next_random", [
    (0, [":- p, not q."], 0.4049341374504143),
    (1, [":- p, q."], 0.7609624449125756),
    (2, [":- p, not q.", ":- p, q."], 0.8354988781294496),
])
def test_constraint_components_preserve_previous_offspring_and_rng(seed, expected, next_random):
    # Recorded before allowing component unions. Their duplicate versions must
    # not change sampling probabilities or the subsequent mutation's RNG state.
    h = generator([":- p, q.", ":- p, not q."], background=["{p;q}."])
    first, second = h.encode([":- p, q."]), h.encode([":- p, not q."])
    rng = random.Random(seed)
    assert component_child(h, first, second, rng) == h.encode(expected)
    assert rng.random() == next_random


def test_component_crossover_preserves_signed_recursive_and_constraint_dependencies():
    h = generator([
        "p.", "p :- base.", "q :- p.", "q :- r.", "r :- q.",
        "s :- not q.", ":- q, s.", "-p.", "t :- -p.",
    ], background=["base."])

    def closed(genome):
        entries = [h.space.entries[i] for i in h._ids(genome)]
        heads = {("base", 0)}.union(*(entry.heads for entry in entries))
        return all(entry.deps <= heads for entry in entries)

    parents = [
        genome for genome in range(1, h.all_clauses + 1)
        if genome.bit_count() <= h.max_clauses and closed(genome)
    ]
    for first, second in combinations(parents, 2):
        for seed in range(3):
            child = component_child(h, first, second, random.Random(seed))
            assert 0 < child.bit_count() <= h.max_clauses
            assert closed(child)
            assert not child & ~(first | second)
            assert child & (first & second) == first & second


def test_background_providers_do_not_join_independent_constraints():
    h = generator([":- p, q.", ":- p, not q.", "keep."], background=["{p;q}."])
    first = h.encode(["keep.", ":- p, q."])
    second = h.encode(["keep.", ":- p, not q."])
    children = {component_child(h, first, second, random.Random(seed)) for seed in range(32)}
    assert h.encode(["keep."]) in children
    assert first | second in children


def test_unchanged_parents_remain_valid_inputs_for_mutation():
    h = generator(["p.", "q."], limit=1)
    first, second = h.encode(["p."]), h.encode(["q."])
    crossover = create_crossover({"name": "component_mix", "probability": 1.0})
    for seed in range(16):
        context = EvolutionContext(h, random.Random(seed))
        assert crossover(first, first, context) == first
        assert crossover(first, second, context) in (first, second)


def test_component_crossover_normalizes_optional_constraints_without_negatives():
    h = generator(["p.", ":- base.", ":- not base."], background=["base."], negatives=False)
    headed = h.encode(["p."])
    constraint = h.encode([":- base."])
    for seed in range(16):
        child = component_child(h, headed, constraint, random.Random(seed))
        assert child in (headed, constraint)
        assert component_child(h, headed | constraint, headed | constraint, random.Random(seed)) == headed
    constraints = h.encode([":- base.", ":- not base."])
    assert component_child(h, constraints, constraints, random.Random(1)) == constraints


def test_component_crossover_preserves_cached_solutions_and_probability_gate():
    h = generator(["p.", "q."])
    first, second = h.encode(["p."]), h.encode(["q."])
    context = EvolutionContext(h, random.Random(1), results={
        second: EvaluationResult(100, True, (1, 0), True, True),
    })
    assert create_crossover({"name": "component_mix", "probability": 1.0})(first, second, context) == second
    assert create_crossover({"name": "component_mix", "probability": 0.0})(first, second, context) is None


@pytest.mark.parametrize("probability", [-0.1, 1.1, True, "0.5", float("nan")])
def test_component_crossover_rejects_invalid_probability(probability):
    with pytest.raises(ValueError, match="probability"):
        create_crossover({"name": "component_mix", "probability": probability})
