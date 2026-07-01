from gentians.evolution.factories import create_selection
from gentians.evolution.individual import Individual
from gentians.evolution.mutations.random_group import mutate_by_random_group
from gentians.evolution.replacements.oldest_or_worst import replace_oldest_or_worst
from gentians.rule_generation.rule_space import RuleSpace


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
        RuleSpace.from_clauses(["a."]),
        1,
        1.0,
        fail_if_called,
        {individual.signature},
    )

    assert mutated is individual
    assert mutated.score == 1.0


def test_mutation_applies_one_unique_edit(monkeypatch):
    individual = Individual(["a.", "b."], 1.0, False, [])
    choices = iter(["append", "c."])

    monkeypatch.setattr("gentians.evolution.mutations.random_group.random.random", lambda: 0.0)
    monkeypatch.setattr(
        "gentians.evolution.mutations.random_group.random.choice",
        lambda _: next(choices),
    )

    def score(program):
        assert len(program) == len(set(program))
        return 2.0, False, []

    mutated = mutate_by_random_group(
        individual,
        RuleSpace.from_clauses(["a.", "b.", "c."]),
        3,
        1.0,
        score,
        {individual.signature},
    )

    assert mutated.program == ["a.", "b.", "c."]
    assert mutated.score == 2.0


def test_replacement_rejects_duplicate_and_non_finite():
    population = [Individual(["a."], 2.0, False, [])]
    signatures = {population[0].signature}

    duplicate = replace_oldest_or_worst(
        population,
        Individual(["a."], 3.0, False, []),
        signatures,
        0.0,
    )
    non_finite = replace_oldest_or_worst(
        population,
        Individual(["b."], float("-inf"), False, []),
        signatures,
        0.0,
    )

    assert duplicate == population
    assert non_finite == population
    assert signatures == {population[0].signature}


def test_replacement_updates_population_signatures(monkeypatch):
    population = [
        Individual(["a."], 3.0, False, []),
        Individual(["b."], 1.0, False, []),
    ]
    signatures = {individual.signature for individual in population}
    monkeypatch.setattr("gentians.evolution.replacements.oldest_or_worst.random.random", lambda: 1.0)

    updated = replace_oldest_or_worst(
        population,
        Individual(["c."], 2.0, False, []),
        signatures,
        0.0,
    )

    assert [individual.program for individual in updated] == [["a."], ["c."]]
    assert signatures == {updated[0].signature, updated[1].signature}
