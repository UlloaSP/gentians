import random

import pytest

from gentians.search.candidates import Candidates
from gentians.search.budget import SearchBudget
from gentians.evaluation.result import EvaluationResult
from gentians.evolution.individual import Individual
from gentians.hypotheses import HypothesisGenerator
from tests.task_helpers import inductive_task, make_clause_space


@pytest.mark.parametrize("constraints_only", [False, True])
def test_renewal_preserves_programs_and_metadata_when_bit_positions_change(constraints_only):
    task = inductive_task(["{a;m;y;z}."], [], [], [], [])
    clauses = [f":- {name}." if constraints_only else f"{name}." for name in "amyz"]
    source = HypothesisGenerator(task, make_clause_space(clauses[1:]), 2)
    target = HypothesisGenerator(task, make_clause_space(clauses), 2)
    champion = Individual(source.encode((clauses[1],)), 0.8, False, (3, 1), 17, True, False)
    other = Individual(source.encode((clauses[3],)), 0.4, False, (1, 0), 9, False, True)
    retained = [other, champion]
    old_results = {
        champion.genome: EvaluationResult(0.8, False, (3, 1), True, False),
        other.genome: EvaluationResult(0.4, False, (1, 0), False, True),
        source.encode((clauses[2],)): EvaluationResult(0.1, False, (0, 1), False, False),
    }
    before_results = dict(old_results)
    rng = random.Random(17)
    before_rng = rng.getstate()

    def evaluate(_genome):
        pytest.fail("renewal must not evaluate retained candidates")

    candidates = Candidates(source, evaluate, rng, SearchBudget(None))
    candidates.results.update(old_results)
    new_retained, new_champion, additions = candidates.renew(target, retained, champion)

    for original, renewed in zip(retained, new_retained, strict=True):
        assert renewed.genome != original.genome
        assert target.render(renewed.genome) == source.render(original.genome)
        assert renewed.birth_order == original.birth_order
        assert candidates.results[renewed.genome] == old_results[original.genome]
        assert candidates.evaluated[renewed.genome] is renewed
    assert new_champion is new_retained[1]
    assert candidates.context.hypotheses is target
    assert candidates.context.results is candidates.results
    assert candidates.context.evaluate == candidates.evaluate
    assert candidates.context.rng is rng
    assert rng.getstate() == before_rng
    assert set(candidates.results) == set(candidates.evaluated) == {
        item.genome for item in new_retained
    }
    assert additions == (target.encode((clauses[0],)) if constraints_only else 0)
    assert old_results == before_results
    assert retained == [other, champion]


def test_failed_renewal_leaves_previous_population_usable():
    task = inductive_task([], [], [], [], [])
    source = HypothesisGenerator(task, make_clause_space(["m.", "z."]), 1)
    target = HypothesisGenerator(task, make_clause_space(["a.", "m."]), 1)
    champion = Individual(source.encode(("m.",)), 0.8, False)
    missing = Individual(source.encode(("z.",)), 0.4, False)
    result = EvaluationResult(0.8, False, (1, 0), False, True)
    results = {champion.genome: result}
    candidates = Candidates(source, lambda _: result, random.Random(17), SearchBudget(None))
    candidates.results.update(results)

    with pytest.raises(KeyError):
        candidates.renew(target, [champion, missing], champion)

    assert candidates.hypotheses.render(champion.genome) == ("m.",)
    assert candidates.hypotheses.render(missing.genome) == ("z.",)
    assert candidates.results == {champion.genome: result}


def test_context_uses_current_space_and_restart_preserves_evaluation_count():
    task = inductive_task([], [], [], [], [])
    source = HypothesisGenerator(task, make_clause_space(["m.", "z."]), 1)
    target = HypothesisGenerator(task, make_clause_space(["a.", "m.", "z."]), 1)
    calls = []

    def evaluate(program):
        text = tuple(map(str, program))
        calls.append(text)
        score = {("m.",): 0.4, ("z.",): 0.2, ("a.",): 0.9}[text]
        return EvaluationResult(score, False, (0, 0), False, True)

    candidates = Candidates(source, evaluate, random.Random(7), SearchBudget(None))
    champion = candidates.admit(source.encode(("m.",)))
    candidates.admit(source.encode(("z.",)))
    _, champion, _ = candidates.renew(target, [champion], champion)
    assert candidates.context.evaluate(champion.genome).score == 0.4
    new_genome = target.encode(("a.",))
    assert candidates.context.evaluate(new_genome).score == 0.9
    child = candidates.admit(new_genome)
    assert child.birth_order == 3
    assert calls == [("m.",), ("z.",), ("a.",)]

    candidates.restart([champion])
    assert candidates.context.results is candidates.results
    assert candidates.context.evaluate(champion.genome).score == 0.4
    assert candidates.admit(new_genome).birth_order == 4
    assert calls == [("m.",), ("z.",), ("a.",), ("a.",)]
