import random


from gentians.evolution.individual import Individual
from gentians.evolution.selections.lexicase_selection import LexicaseSelection
from gentians.algorithms import steady_state_genetic as search
from gentians.arguments import Arguments
from gentians.evaluation.result import EvaluationResult
from tests.task_helpers import inductive_task, make_clause_space








def test_normal_lexicase_keeps_existing_rng_consumption():
    # Filtering to one candidate consumed only shuffle randomness before the change.
    poor = Individual(1, 1.0, False, (0, 1))
    safe = Individual(2, 2.0, False, (1, 0))
    rng = random.Random(39)
    expected = random.Random(39)
    expected.shuffle([(1, True), (1, False)])
    expected.shuffle([(1, True), (1, False)])
    assert LexicaseSelection()([poor, safe], 2, rng) == [safe, safe]
    assert rng.getstate() == expected.getstate()
    # A tie consumes the ordinary choice draw, including a singleton with no cases.
    empty = Individual(4, 0.0, False)
    expected.choice([empty])
    expected.choice([empty])
    assert LexicaseSelection()([empty], 2, rng) == [empty, empty]
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
