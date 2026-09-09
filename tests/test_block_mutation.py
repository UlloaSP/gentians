import random

import pytest

from gentians.arguments import Arguments
from gentians.evaluation import create_evaluator
from gentians.evaluation.result import EvaluationResult
from gentians.evolution.context import EvolutionContext
from gentians.evolution.mutations import create_mutation
from gentians.evolution.mutations.random_group import RandomGroupMutation
from gentians.hypotheses import HypothesisGenerator
from tests.task_helpers import example, inductive_task, make_clause_space


def generator(rules, *, background=(), max_clauses=10):
    task = inductive_task(list(background), [example(("goal", ""), True)],
                          [example(("bad", ""), False)], [], [])
    return HypothesisGenerator(task, make_clause_space(rules), max_clauses)


def choose_replacement(monkeypatch, h, source, replacement):
    # Fix only sampling. Exercise the real dependency transition and validation.
    source_id, replacement_id = h.clause_ids[source], h.clause_ids[replacement]
    random_ids = h._random_ids
    monkeypatch.setattr(h, "_random_ids", lambda mask, rng:
                        iter([source_id]) if mask & (1 << source_id) else random_ids(mask, rng))
    monkeypatch.setattr(h, "_random_available", lambda excluded, rng: iter([replacement_id]))


def test_factory_kept_with_one_strategy_and_two_independent_defaults():
    mutation = create_mutation(Arguments().mutation)
    assert isinstance(mutation, RandomGroupMutation)
    assert mutation.random_jump_probability == 0.1
    assert mutation.complete_generator_removal_probability == 0.1
    sparse = create_mutation({"name": "random_group", "probability": 1})
    assert sparse.random_jump_probability == sparse.complete_generator_removal_probability == 0.1
    with pytest.raises(ValueError, match="Unknown mutation strategy"):
        create_mutation({"name": "structural_neighbor"})


def test_experiment_matrix_explicitly_records_new_mutation_defaults():
    from benchmarks.run_experiments import DEFAULT_CONFIG, load_config

    _, experiments = load_config(DEFAULT_CONFIG)
    assert len(experiments) == 18
    for experiment in experiments:
        config = dict(Arguments().mutation)
        config.update({key.removeprefix("mutation."): value
                       for key, value in experiment["overrides"].items()
                       if key.startswith("mutation.")})
        assert config["complete_generator_removal_probability"] == 0.1
        assert config["random_jump_probability"] == (
            1 if experiment["id"] in {"mutation-ablation/global-head", "mutation-ablation/unguided-global"}
            else 0.1)
        assert isinstance(create_mutation(config), RandomGroupMutation)


@pytest.mark.parametrize("key", ["probability", "random_jump_probability",
                                 "complete_generator_removal_probability"])
@pytest.mark.parametrize("value", [True, "0.1", -0.1, 1.1, float("nan"), float("inf")])
def test_all_mutation_probabilities_are_validated(key, value):
    with pytest.raises(ValueError, match="between 0 and 1"):
        create_mutation({"name": "random_group", "probability": 1, key: value})


def test_removal_cascades_without_inserting_an_alternative_provider():
    h = generator(["p.", "p :- base.", "q :- p.", "r :- q.", "keep."], background=["base."])
    before = h.encode(["p.", "q :- p.", "r :- q.", "keep."])
    after = h.remove(before, random.Random(1), sources=h.encode(["p."]))
    assert h.render(after) == ("keep.",)
    assert after & ~before == 0


@pytest.mark.parametrize("background,additional", [(["p."], []),
                                                   (["base."], ["p :- base."])])
def test_removal_preserves_consumers_with_existing_alternative(background, additional):
    h = generator(["p.", "q :- p.", *additional], background=background)
    before = h.all_clauses
    after = h.remove(before, random.Random(1), sources=h.encode(["p."]))
    assert after == before & ~h.encode(["p."])


def test_removal_handles_signed_dependencies_and_recursive_blocks():
    h = generator(["p.", "-p.", "a :- -p, b.", "b :- a.", "keep."])
    after = h.remove(h.all_clauses, random.Random(1), sources=h.encode(["-p."]))
    assert set(h.render(after)) == {"p.", "keep."}


def test_removal_preserves_unrelated_providers_and_rejects_empty_block():
    h = generator(["p.", "q :- p."])
    assert h.remove(h.all_clauses, random.Random(1), sources=h.encode(["p."])) is None
    after = h.remove(h.all_clauses, random.Random(1), sources=h.encode(["q :- p."]))
    assert h.render(after) == ("p.",)


def test_removal_checks_protection_on_the_entire_block():
    h = generator(["p.", "q :- p.", "keep."])
    assert h.remove(h.all_clauses, random.Random(1), mutable=h.encode(["p."])) is None


@pytest.mark.parametrize("limit,success", [(3, False), (4, True)])
def test_append_adds_transitive_support_and_checks_final_size(monkeypatch, limit, success):
    h = generator(["keep.", "goal :- helper.", "helper :- base.", "base."], max_clauses=limit)
    root = h.clause_ids["goal :- helper."]
    monkeypatch.setattr(h, "_random_available", lambda excluded, rng: iter([root]))
    before = h.encode(["keep."])
    after = h.append(before, random.Random(1))
    assert (after == h.all_clauses) if success else (after is None)
    h.set_available_clauses(h.encode(["keep.", "goal :- helper."]))
    assert h.append(before, random.Random(1)) is None


def test_replace_preserves_consumers_supported_by_the_new_head(monkeypatch):
    h = generator(["p.", "p :- base.", "q :- p.", "keep."], background=["base."])
    before = h.encode(["p.", "q :- p.", "keep."])
    choose_replacement(monkeypatch, h, "p.", "p :- base.")
    after = h.replace(before, random.Random(1), same_head=True)
    assert set(h.render(after)) == {"p :- base.", "q :- p.", "keep."}


def test_replace_removes_old_consumers_and_closes_new_block(monkeypatch):
    h = generator(["p.", "q :- p.", "r :- q.", "keep.", "new :- helper.", "helper."],
                  max_clauses=4)
    before = h.encode(["p.", "q :- p.", "r :- q.", "keep."])
    choose_replacement(monkeypatch, h, "p.", "new :- helper.")
    after = h.replace(before, random.Random(1))
    assert set(h.render(after)) == {"keep.", "new :- helper.", "helper."}
    assert h.replace(before, random.Random(1), mutable=h.encode(["p.", "new :- helper.", "helper."])) is None


def test_replace_cannot_reintroduce_removed_block_as_support(monkeypatch):
    h = generator(["p.", "q :- p.", "keep.", "new :- q."])
    before = h.encode(["p.", "q :- p.", "keep."])
    choose_replacement(monkeypatch, h, "p.", "new :- q.")
    assert h.replace(before, random.Random(1)) is None


def test_constraint_removal_can_recover_positive():
    task = inductive_task(["p.", "{q}."], [example(("p", "q"), True)],
                          [example(("q", ""), False)], [], [])
    h = HypothesisGenerator(task, make_clause_space([":- p.", ":- q."]), 2)
    before = h.all_clauses
    after = h.remove(before, random.Random(1), sources=h.encode([":- p."]))
    evaluate = create_evaluator(task, {"scoring": "cov_program"})
    assert not evaluate(h.program(before)).is_complete
    assert evaluate(h.program(after)).is_solution


@pytest.mark.parametrize("source,replacement", [
    (":- p.", "q."),
    ("q.", ":- p."),
])
def test_same_kind_replacement_preserves_root_role(monkeypatch, source, replacement):
    h = generator([source, replacement], background=["p.", "q."])
    choose_replacement(monkeypatch, h, source, replacement)
    assert h.replace(h.encode([source]), random.Random(1), same_kind=True) is None


def test_headed_replacement_can_remove_dependent_constraints(monkeypatch):
    h = generator(["p.", "q.", ":- p.", "keep."])
    before = h.encode(["p.", ":- p.", "keep."])
    choose_replacement(monkeypatch, h, "p.", "q.")
    after = h.replace(before, random.Random(1), same_kind=True)
    assert set(h.render(after)) == {"q.", "keep."}


def test_same_kind_replacement_does_not_scan_without_matching_alternatives(monkeypatch):
    h = generator([":- p.", "q."], background=["p."])
    def unexpected(*args):
        pytest.fail("No matching alternatives: replacement must not scan")
    monkeypatch.setattr(h, "_random_available", unexpected)
    assert h.replace(h.encode([":- p."]), random.Random(1), same_kind=True) is None


def test_complete_candidate_never_replaces_or_adds_headed_rules():
    h = generator(["goal.", "bad.", "other.", ":- bad."], max_clauses=3)
    before = h.encode(["goal.", "bad."])
    results = {before: EvaluationResult(0, False, (1, 1), True, False)}
    mutation = RandomGroupMutation(1, 1, 0)
    for seed in range(30):
        after = mutation(before, EvolutionContext(h, random.Random(seed), results=results)).genome
        assert after & ~h.constraint_clauses == before


def test_complete_generator_deletion_is_one_configurable_attempt(monkeypatch):
    h = generator(["goal.", "bad.", "consumer :- bad.", ":- bad."])
    before = h.all_clauses
    bad = h.clause_ids["bad."]
    monkeypatch.setattr(h, "_random_ids", lambda mask, rng: iter([bad] if mask & (1 << bad) else []))
    result = EvaluationResult(0, False, (1, 1), True, False)
    proposal = RandomGroupMutation(1, 0, 1)(
        before, EvolutionContext(h, random.Random(1), results={before: result}))
    assert proposal.operation == "remove"
    assert h.render(proposal.genome) == ("goal.",)


def test_complete_candidate_has_no_unrestricted_fallback():
    h = generator(["goal | bad.", "goal."], max_clauses=1)
    before = h.encode(["goal | bad."])
    results = {before: EvaluationResult(0, False, (1, 1), True, False)}
    for seed in range(10):
        after = RandomGroupMutation(1, 1, 1)(
            before, EvolutionContext(h, random.Random(seed), results=results))
        assert after.genome == before


@pytest.mark.parametrize("jump", [0, 1])
def test_incomplete_constraint_only_mutation_can_replace_without_relaxation(jump):
    task = inductive_task(["p.", "{q}."], [example(("p", "q"), True)],
                          [example(("q", ""), False)], [], [])
    h = HypothesisGenerator(task, make_clause_space([":- p.", ":- q."]), 1)
    before = h.encode([":- p."])
    evaluate = create_evaluator(task, {"scoring": "cov_program"})
    result = evaluate(h.program(before))
    assert not result.is_complete
    after = RandomGroupMutation(1, jump)(
        before, EvolutionContext(h, random.Random(1), results={before: result}))
    assert after.operation == "replace"
    assert h.render(after.genome) == (":- q.",)
    assert evaluate(h.program(after.genome)).is_solution


def test_incomplete_does_not_append_constraints():
    h = generator(["goal.", ":- goal."], max_clauses=2)
    before = h.encode(["goal."])
    results = {before: EvaluationResult(0, False, (0, 1), False, False)}
    for seed in range(10):
        after = RandomGroupMutation(1, 1)(before, EvolutionContext(h, random.Random(seed), results=results))
        assert after.genome == before


def test_block_transitions_preserve_invariants_across_seeds():
    h = generator(["p.", "q :- p.", "q :- base.", "r :- q.", "keep.", ":- r."],
                  background=["base."], max_clauses=4)
    before = h.encode(["p.", "q :- p.", "r :- q.", "keep."])
    for seed in range(30):
        for operation in ("append", "remove", "replace"):
            after = getattr(h, operation)(before, random.Random(seed))
            if after is not None:
                heads, deps = h._summary(after)
                assert 0 < after.bit_count() <= h.max_clauses
                assert not after & ~h.available_clauses
                assert not deps & ~(heads | h.background_mask)
                if operation == "remove":
                    assert after & ~before == 0


@pytest.mark.parametrize("limit", [1, 2])
def test_positive_only_constraint_candidate_can_acquire_a_headed_block(limit):
    task = inductive_task(["base."], [example(("goal", ""), True)], [], [], [])
    h = HypothesisGenerator(task, make_clause_space(["goal.", ":- base."]), limit)
    before = h.encode([":- base."])
    results = {before: EvaluationResult(0, False, (0, 0), False, True)}
    for seed in range(10):
        after = RandomGroupMutation(1, 1)(before, EvolutionContext(h, random.Random(seed), results=results))
        assert h.render(after.genome) == ("goal.",)


def test_removal_cache_forbids_removed_block_not_the_entire_space():
    h = generator(["a.", "b.", *[f"z({i})." for i in range(1000)]])
    before = h.encode(["a.", "b."])
    h.remove(before, random.Random(1), sources=h.encode(["a."]))
    assert h._build_cache
    assert all(forbidden == h.encode(["a."]) for _, _, forbidden in h._build_cache)
