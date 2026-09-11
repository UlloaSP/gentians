import random


from gentians.evolution.individual import Individual
from gentians.evolution.operator_types import MutationProposal
from gentians.evolution.selections.lexicase_selection import LexicaseSelection
from gentians.algorithms import steady_state_genetic as search
from gentians.arguments import Arguments
from gentians.evaluation.result import EvaluationResult
from tests.task_helpers import inductive_task, make_clause_space








def test_lexicase_draws_each_parent_without_replacement():
    poor = Individual(1, 1.0, False, (0, 1))
    safe = Individual(2, 2.0, False, (1, 0))
    rng = random.Random(39)
    assert LexicaseSelection()([poor, safe], 2, rng) == [safe, poor]


def test_duplicate_crossover_base_is_mutated_without_reselection(monkeypatch):
    selection_calls = []
    crossover_calls = []
    mutation_calls = []
    start = ("start.",)
    other = ("other.",)
    mutated = ("mutated.",)
    args = Arguments(
        random_seed=3,
        iterations_genetic=1,
        population={"name": "random", "size": 2},
        crossover={"name": "component_mix", "probability": 1.0},
    )

    monkeypatch.setattr(
        search,
        "create_population",
        lambda config: lambda context: [
            context.hypotheses.encode(start),
            context.hypotheses.encode(other),
        ],
    )

    def select(population, count, rng):
        selection_calls.append(tuple(item.genome for item in population))
        return population[:count]

    monkeypatch.setattr(search, "create_selection", lambda config: select)

    def cross(first, second, context):
        crossover_calls.append((first, second))
        return context.hypotheses.encode(start)

    monkeypatch.setattr(search, "create_crossover", lambda config: cross)

    def mutate(genome, context, force=False):
        mutation_calls.append(genome)
        assert force is True
        return MutationProposal(context.hypotheses.encode(mutated))

    monkeypatch.setattr(search, "create_mutation", lambda config: mutate)
    monkeypatch.setattr(
        search,
        "create_evaluator",
        lambda task, config, *, space: lambda candidate: EvaluationResult(
            1.0 if tuple(map(str, candidate)) == mutated else 0.0,
            False,
            (0, 0),
            False,
            True,
        ),
    )

    result = search.steady_state_genetic_search(
        args,
        inductive_task([], [], [], [], [], max_program_clauses=1),
        make_clause_space([*start, *other, *mutated]),
    )

    assert result.hypothesis == mutated
    assert len(selection_calls) == 1
    assert len(crossover_calls) == 1
    assert len(mutation_calls) == 1


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
