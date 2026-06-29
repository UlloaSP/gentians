from gentians.evolution.factories import create_selection
from gentians.evolution.individual import Individual
from gentians.evolution.mutations.random_group import mutate_by_random_group


def test_tournament_selection_returns_distinct_signatures_when_possible(monkeypatch):
    population = [
        Individual(["a."], 2.0, False, []),
        Individual(["b."], 1.0, False, []),
    ]

    def same_parent(population, tournament_size, prob_selecting_fittest):
        return population[0]

    monkeypatch.setattr("gentians.evolution.factories.tournament_selection", same_parent)

    selected_a, selected_b = create_selection(
        {
            "name": "tournament",
            "tournament_size": 2,
            "prob_selecting_fittest": 1.0,
        }
    )(population)

    assert selected_a.signature != selected_b.signature


def test_mutation_skips_fitness_when_signature_does_not_change(monkeypatch):
    individual = Individual(["a."], 1.0, False, [])

    monkeypatch.setattr("gentians.evolution.mutations.random_group.random.random", lambda: 0.0)
    monkeypatch.setattr("gentians.evolution.mutations.random_group.random.choice", lambda _: "a.")

    def fail_if_called(program):
        raise AssertionError("fitness should not run for no-op mutation")

    mutated = mutate_by_random_group(
        individual,
        ["a."],
        1,
        1.0,
        fail_if_called,
        {individual.signature},
    )

    assert mutated is individual
    assert mutated.score == 1.0
