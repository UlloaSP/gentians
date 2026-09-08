import random

import pytest

from gentians.evolution.individual import Individual
from gentians.evolution.reproduction import ReproductiveHistory
from gentians.evolution.selections.lexicase_selection import LexicaseSelection
from gentians.algorithms import steady_state_genetic as search
from gentians.arguments import Arguments
from gentians.evaluation.result import EvaluationResult
from tests.task_helpers import inductive_task, make_clause_space


def test_history_counts_opportunities_once_per_parent_and_rewards_strict_improvement():
    first = Individual(1, 2.0, False)
    second = Individual(2, 4.0, False)
    better = Individual(4, 5.0, False)
    history = ReproductiveHistory()
    assert history.value(first.genome) == 0.5
    history.observe(first, second, better)
    assert history.value(first.genome) == pytest.approx(2 / 3)
    assert history.value(second.genome) == pytest.approx(2 / 3)
    history.observe(first, first, None)
    history.observe(first, second, better, duplicate=True)
    history.observe(first, second, second)
    assert history.attempts(first.genome) == 4
    assert history.attempts(second.genome) == 3
    assert history.value(first.genome) == pytest.approx(2 / 6)
    assert history.value(second.genome) == pytest.approx(2 / 5)
    assert history.attempts(better.genome) == 0


def test_decay_reduces_evidence_toward_prior_and_retain_forgets_absent_parents():
    first = Individual(1, 2.0, False)
    second = Individual(2, 4.0, False)
    history = ReproductiveHistory()
    history.observe(first, second, Individual(4, 5.0, False))
    history.decay()
    assert history.attempts(1) == 0.5
    assert history.value(1) == pytest.approx(1.5 / 2.5)
    history.retain([1])
    assert history.attempts(2) == 0
    assert history.value(2) == 0.5
    with pytest.raises(ValueError):
        history.decay(1.1)


def test_remap_keeps_credit_for_retained_programs_not_old_bit_positions():
    history = ReproductiveHistory()
    history.observe(Individual(1, 1.0, False), Individual(2, 2.0, False),
                    Individual(4, 3.0, False))
    history.remap({1: 8})
    assert history.attempts(8) == 1
    assert history.value(8) == pytest.approx(2 / 3)
    assert history.attempts(1) == history.attempts(2) == 0


def test_normal_lexicase_keeps_existing_rng_consumption():
    # Filtering to one candidate consumed only shuffle randomness before the change.
    poor = Individual(1, 1.0, False, (0, 1))
    safe = Individual(2, 2.0, False, (1, 0))
    rng = random.Random(39)
    expected = random.Random(39)
    expected.shuffle([(1, True), (1, False)])
    expected.shuffle([(1, True), (1, False)])
    assert LexicaseSelection()([poor, safe], rng) == (safe, safe)
    assert rng.getstate() == expected.getstate()
    # A tie consumes the ordinary choice draw, including a singleton with no cases.
    empty = Individual(4, 0.0, False)
    expected.choice([empty])
    expected.choice([empty])
    assert LexicaseSelection()([empty], rng) == (empty, empty)
    assert rng.getstate() == expected.getstate()


def test_search_stops_initialization_at_first_perfect_candidate(monkeypatch):
    monkeypatch.setattr(
        search,
        "create_population",
        lambda config: lambda context: [
            context.hypotheses.encode((text,)) for text in ("win.", "unused.")
        ],
    )
    evaluated = []

    def evaluate(program):
        evaluated.append(tuple(map(str, program)))
        return EvaluationResult(1.0, True, (0, 0), True, True)

    monkeypatch.setattr(search, "create_evaluator", lambda task, config, *, space: evaluate)
    result = search.steady_state_genetic_search(
        Arguments(random_seed=2, iterations_genetic=1),
        inductive_task([], [], [], [], [], max_program_clauses=1),
        make_clause_space(["win.", "unused."]),
    )
    assert result.is_solution
    assert result.hypothesis == ("win.",)
    assert evaluated == [("win.",)]
