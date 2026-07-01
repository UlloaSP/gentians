import pytest

from gentians.arguments import Arguments
from gentians.evolution.algorithms.genetic import genetic_solver
from gentians.evolution.crossovers.set_mix import set_mix_crossover
from gentians.evolution.factories import create_selection
from gentians.evolution.individual import Individual
from gentians.evolution.mutations.random_group import mutate_by_random_group
from gentians.evolution.populations.random_initialization import initialize_population
from gentians.evolution.program_sampler import ProgramSampler
from gentians.evolution.replacements.oldest_or_worst import replace_oldest_or_worst
from gentians.rule_generation.program import Example, Program
from gentians.rule_generation.rule_space import RuleSpace


def test_genetic_solver_returns_best_candidate_without_marking_exact_solution():
    population = [
        Individual(["low."], 1.0, False, []),
        Individual(["high."], 2.0, False, []),
    ]

    def initialize(max_program_clauses, rule_space, evaluate_score):
        return population, False

    def select(population):
        return population[0], population[1]

    def crossover(parent_a, parent_b, evaluate_score, known_signatures, max_program_clauses):
        return parent_a, parent_b

    def mutation(individual, rule_space, max_program_clauses, evaluate_score, known_signatures):
        return individual

    def replacement(population, individual, population_signatures):
        return population

    program, score, best_found = genetic_solver(
        RuleSpace.from_clauses(["low.", "high."]),
        Arguments(iterations_genetic=0),
        lambda program: (0.0, False, []),
        initialize,
        select,
        crossover,
        mutation,
        replacement,
    )

    assert program == ["high."]
    assert score == 2.0
    assert best_found is False


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


def test_mutation_retries_duplicate_before_fitness(monkeypatch):
    individual = Individual(["a."], 1.0, False, [])
    choices = iter(["replace", "b.", "replace", "c."])
    metrics = []

    monkeypatch.setattr("gentians.evolution.mutations.random_group.random.random", lambda: 0.0)
    monkeypatch.setattr(
        "gentians.evolution.mutations.random_group.random.choice",
        lambda _: next(choices),
    )
    monkeypatch.setattr("gentians.evolution.mutations.random_group.random.randrange", lambda _: 0)
    monkeypatch.setattr(
        "gentians.evolution.mutations.random_group.record_metric",
        lambda kind, row: metrics.append(row),
    )

    calls = []

    def score(program):
        calls.append(program)
        return 2.0, False, []

    mutated = mutate_by_random_group(
        individual,
        RuleSpace.from_clauses(["a.", "b.", "c."]),
        1,
        1.0,
        score,
        {individual.signature, ("b.",)},
    )

    assert mutated.program == ["c."]
    assert calls == [["c."]]
    assert metrics[-1]["duplicate_population"] is False
    assert metrics[-1]["duplicate_attempts"] == 1


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


def test_replacement_rejects_duplicate_with_stale_signature_set():
    population = [Individual(["a."], 2.0, False, [])]
    signatures = set()

    updated = replace_oldest_or_worst(
        population,
        Individual(["a."], 3.0, False, []),
        signatures,
        0.0,
    )

    assert updated == population
    assert [individual.program for individual in updated] == [["a."]]
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


def test_replacement_keeps_population_sorted_when_replacing_oldest(monkeypatch):
    population = [
        Individual(["a."], 3.0, False, []),
        Individual(["b."], 2.0, False, []),
        Individual(["c."], 1.0, False, []),
    ]
    population[1].generated_timestamp = 0.0
    population[0].generated_timestamp = 1.0
    population[2].generated_timestamp = 2.0
    signatures = {individual.signature for individual in population}
    monkeypatch.setattr("gentians.evolution.replacements.oldest_or_worst.random.random", lambda: 0.0)

    updated = replace_oldest_or_worst(
        population,
        Individual(["d."], 2.5, False, []),
        signatures,
        1.0,
    )

    assert [individual.score for individual in updated] == [3.0, 2.5, 1.0]
    assert signatures == {updated[0].signature, updated[1].signature, updated[2].signature}


def test_program_sampler_repairs_missing_dependency():
    rules = [
        "heads(V0):- coin(V0),not tails(V0).",
        "tails(V0):- coin(V0),not heads(V0).",
    ]
    program = Program(
        ["coin(c1)."],
        [Example(("heads(c1)", "tails(c1)"), True)],
        [],
        [],
        [],
    )
    sampler = ProgramSampler(program, RuleSpace.from_clauses(rules))

    repaired = sampler.repair([rules[0]], 2)

    assert repaired == sorted(rules)
    assert sampler.is_closed(repaired)


def test_crossover_does_not_evaluate_unrepaired_sampler_child():
    parent_a = Individual(["a."], 1.0, False, [])
    parent_b = Individual(["b."], 2.0, False, [])

    class RejectingSampler:
        def repair(self, *args, **kwargs):
            return None

        def sample(self, *args, **kwargs):
            return None

    def fail_if_called(program):
        raise AssertionError("fitness should not run for unrepaired child")

    child_a, child_b = set_mix_crossover(
        parent_a,
        parent_b,
        fail_if_called,
        1.0,
        {parent_a.signature, parent_b.signature},
        1,
        RejectingSampler(),
    )

    assert child_a.signature in {parent_a.signature, parent_b.signature}
    assert child_b.signature in {parent_a.signature, parent_b.signature}


def test_crossover_counts_parent_children_as_duplicates(monkeypatch):
    parent_a = Individual(["a."], 1.0, False, [])
    parent_b = Individual(["b."], 2.0, False, [])
    metrics = []

    class ParentSampler:
        def repair(self, *args, **kwargs):
            return ["a."]

        def sample(self, *args, **kwargs):
            return ["a."]

    monkeypatch.setattr(
        "gentians.evolution.crossovers.set_mix.record_metric",
        lambda kind, row: metrics.append(row),
    )

    set_mix_crossover(
        parent_a,
        parent_b,
        lambda program: (3.0, False, []),
        1.0,
        {parent_a.signature, parent_b.signature},
        1,
        ParentSampler(),
    )

    assert metrics[-1]["children_same_as_parent"] == 0
    assert metrics[-1]["children_duplicate_parent"] == 2
    assert metrics[-1]["children_duplicate_population"] == 0


def test_initialization_stops_when_exact_solution_found():
    calls = []

    def score(program):
        calls.append(program)
        return 1.0, True, []

    population, best_found = initialize_population(
        1,
        RuleSpace.from_clauses(["a."]),
        5,
        score,
    )

    assert best_found is True
    assert len(population) == 1
    assert len(calls) == 1


def test_initialization_does_not_fallback_to_raw_when_sampler_fails():
    class RejectingSampler:
        def sample(self, *args, **kwargs):
            return None

    def fail_if_called(program):
        raise AssertionError("fitness should not run for raw fallback")

    with pytest.raises(RuntimeError, match="dependency-closed"):
        initialize_population(
            1,
            RuleSpace.from_clauses(["a."]),
            1,
            fail_if_called,
            RejectingSampler(),
        )
