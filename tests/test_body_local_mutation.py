import random

import pytest

from gentians.evaluation import create_evaluator
from gentians.evolution.context import EvolutionContext
from gentians.evolution.mutations import create_mutation
from gentians.evolution.mutations.random_group import RandomGroupMutation
from gentians.hypotheses import HypothesisGenerator
from gentians.hypotheses.body_neighborhood import BodyNeighborhood
from tests.task_helpers import example, inductive_task, make_clause_space


def test_index_finds_one_body_element_edit_with_exact_head():
    rules = [":- p(X), q(X).", ":- q(X), p(X), r(X).", ":- p(X).",
             ":- p(X), s(X).", ":- r(X), s(X).", "h(X) :- p(X), q(X).",
             ":- p(X), q(Y)."]
    space = make_clause_space(rules)
    index = BodyNeighborhood(space)
    source = space.clauses.index(rules[0])
    assert {space.clauses[i] for i in index.neighbors(source)} == {
        rules[1], rules[2], rules[3], rules[6]}
    # Linear number of postings, not a stored all-pairs neighbor graph.
    assert sum(map(len, index.full.values())) == len(rules)
    assert sum(map(len, index.holes.values())) <= sum(len(e.statement.body) for e in space.entries)


def test_index_preserves_multiplicity_and_does_not_infer_variable_renaming():
    space = make_clause_space([":- p(X), p(X).", ":- p(X).", ":- p(Y), q(Y)."])
    index = BodyNeighborhood(space)
    ids = {s: i for i, s in enumerate(space.clauses)}
    assert index.neighbors(ids[":- p(X), p(X)."]) == (ids[":- p(X)."],)


def task_and_generator(rules, *, max_clauses=1):
    task = inductive_task(["p.", "{q}.", "{r}."], [example(("p", "q"), True)],
                          [example(("q", ""), False)], [], [])
    return task, HypothesisGenerator(task, make_clause_space(rules), max_clauses)


def test_local_replacement_can_recover_positive_and_keep_nonempty_program():
    task = inductive_task(["p.", "{q}.", "r."], [example(("p,r", "q"), True)],
                          [example(("q", ""), False)], [], [])
    h = HypothesisGenerator(task, make_clause_space([":- p, r.", ":- q, r."]), 1)
    before = h.encode([":- p, r."])
    evaluate = create_evaluator(task, {"scoring": "cov_program"})
    result = evaluate(h.program(before))
    assert not result.is_complete
    after = RandomGroupMutation(1, body_local_probability=1)(
        before, EvolutionContext(h, random.Random(1), results={before: result}))
    assert after.operation == "replace"
    assert h.render(after.genome) == (":- q, r.",)
    assert evaluate(h.program(after.genome)).is_complete


def test_local_transition_respects_pool_size_and_dependency_protection():
    task, h = task_and_generator([":- p.", ":- p, helper.", "helper."], max_clauses=1)
    before = h.encode([":- p."])
    assert h.replace(before, random.Random(1), body_local=True) is None
    h.max_clauses = 2
    assert h.replace(before, random.Random(1), body_local=True,
                     mutable=h.constraint_clauses) is None
    after = h.replace(before, random.Random(1), body_local=True)
    assert set(h.render(after)) == {":- p, helper.", "helper."}
    index = h.body_neighborhood
    h.set_pool(h.encode([":- p.", "helper."]))
    assert h.replace(before, random.Random(1), body_local=True) is None
    assert h.body_neighborhood is index


def test_empty_local_neighborhood_falls_back_to_global():
    _, h = task_and_generator([":- p, q.", ":- r."])
    before = h.encode([":- p, q."])
    proposal = RandomGroupMutation(1, body_local_probability=1)(
        before, EvolutionContext(h, random.Random(1)))
    assert h.render(proposal.genome) == (":- r.",)


def test_disabled_locality_never_builds_index():
    _, h = task_and_generator([":- p.", ":- q."])
    before = h.encode([":- p."])
    RandomGroupMutation(1)(before, EvolutionContext(h, random.Random(1)))
    assert "body_neighborhood" not in h.__dict__


@pytest.mark.parametrize("draw,expected", [(0.79, True), (0.8, False)])
def test_eighty_percent_draw_selects_local_or_global(monkeypatch, draw, expected):
    _, h = task_and_generator([":- p.", ":- q."])
    before, after = h.encode([":- p."]), h.encode([":- q."])
    rng = random.Random(1)
    draws = iter([0.0, 0.5, draw])  # Mutation gate, head permission, body locality.
    monkeypatch.setattr(rng, "random", lambda: next(draws))
    attempts = []
    def replace(genome, rng, **kwargs):
        attempts.append(kwargs["body_local"])
        return after
    monkeypatch.setattr(h, "replace", replace)
    proposal = RandomGroupMutation(1, body_local_probability=0.8)(before, EvolutionContext(h, rng))
    assert proposal.genome == after
    assert attempts == [expected]


@pytest.mark.parametrize("value", [True, -0.1, 1.1, float("nan"), "0.8"])
def test_factory_validates_body_local_probability(value):
    with pytest.raises(ValueError, match="body_local_probability"):
        create_mutation({"name": "random_group", "probability": 1,
                         "body_local_probability": value})
