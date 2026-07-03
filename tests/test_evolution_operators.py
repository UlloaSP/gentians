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
        Individual(["low."], 1.0, False),
        Individual(["high."], 2.0, False),
    ]

    def initialize(max_program_clauses, evaluate_score):
        return population, False

    def select(population):
        return population[0], population[1]

    def crossover(parent_a, parent_b, evaluate_score, known_signatures, max_program_clauses):
        return parent_a, parent_b

    def mutation(individual, max_program_clauses, evaluate_score, known_signatures):
        return individual

    def replacement(population, individual, population_signatures):
        return population

    program, score, best_found = genetic_solver(
        Arguments(iterations_genetic=0),
        lambda program: (0.0, False),
        initialize,
        select,
        crossover,
        mutation,
        replacement,
    )

    assert program == ["high."]
    assert score == 2.0
    assert best_found is False


def test_genetic_solver_returns_single_candidate_without_evolution():
    population = [Individual(["only."], 1.0, False)]

    def initialize(max_program_clauses, evaluate_score):
        return population, False

    def fail_if_called(*args, **kwargs):
        raise AssertionError("single-candidate population should return directly")

    program, score, best_found = genetic_solver(
        Arguments(iterations_genetic=10),
        lambda program: (0.0, False),
        initialize,
        fail_if_called,
        fail_if_called,
        fail_if_called,
        fail_if_called,
    )

    assert program == ["only."]
    assert score == 1.0
    assert best_found is False


def test_tournament_selection_returns_distinct_signatures_when_possible(monkeypatch):
    population = [
        Individual(["a."], 2.0, False),
        Individual(["b."], 1.0, False),
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


def test_selection_accepts_single_individual_population():
    population = [Individual(["a."], 1.0, False)]

    selected_a, selected_b = create_selection(
        {
            "name": "fittest",
            "pick_uniform": True,
        }
    )(population)

    assert selected_a is population[0]
    assert selected_b is population[0]


def _sampler(rules: list[str]) -> ProgramSampler:
    return ProgramSampler(Program([], [], [], [], []), RuleSpace.from_clauses(rules))


def test_mutation_skips_fitness_when_signature_does_not_change(monkeypatch):
    individual = Individual(["a."], 1.0, False)

    monkeypatch.setattr("gentians.evolution.mutations.random_group.random.random", lambda: 0.0)
    monkeypatch.setattr("gentians.evolution.mutations.random_group.random.choice", lambda _: "a.")

    def fail_if_called(program):
        raise AssertionError("fitness should not run for no-op mutation")

    mutated = mutate_by_random_group(
        individual,
        1,
        1.0,
        fail_if_called,
        {individual.signature},
        _sampler(["a."]),
    )

    assert mutated is individual
    assert mutated.score == 1.0


def test_mutation_applies_one_unique_edit(monkeypatch):
    individual = Individual(["a.", "b."], 1.0, False)
    choices = iter(["append", "c."])

    monkeypatch.setattr("gentians.evolution.mutations.random_group.random.random", lambda: 0.0)
    monkeypatch.setattr(
        "gentians.evolution.mutations.random_group.random.choice",
        lambda _: next(choices),
    )

    def score(program):
        assert len(program) == len(set(program))
        return 2.0, False

    mutated = mutate_by_random_group(
        individual,
        3,
        1.0,
        score,
        {individual.signature},
        _sampler(["a.", "b.", "c."]),
    )

    assert mutated.program == ["a.", "b.", "c."]
    assert mutated.score == 2.0


def test_mutation_retries_duplicate_before_fitness(monkeypatch):
    individual = Individual(["a."], 1.0, False)
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
    monkeypatch.setattr(
        "gentians.evolution.mutations.random_group.metric_enabled",
        lambda kind: True,
    )

    calls = []

    def score(program):
        calls.append(program)
        return 2.0, False

    mutated = mutate_by_random_group(
        individual,
        1,
        1.0,
        score,
        {individual.signature, ("b.",)},
        _sampler(["a.", "b.", "c."]),
    )

    assert mutated.program == ["c."]
    assert calls == [["c."]]
    assert metrics[-1]["duplicate_population"] is False
    assert metrics[-1]["duplicate_attempts"] == 1


def test_replacement_rejects_duplicate_and_non_finite():
    population = [Individual(["a."], 2.0, False)]
    signatures = {population[0].signature}

    duplicate = replace_oldest_or_worst(
        population,
        Individual(["a."], 3.0, False),
        signatures,
        0.0,
    )
    non_finite = replace_oldest_or_worst(
        population,
        Individual(["b."], float("-inf"), False),
        signatures,
        0.0,
    )

    assert duplicate == population
    assert non_finite == population
    assert signatures == {population[0].signature}


def test_replacement_updates_population_signatures(monkeypatch):
    population = [
        Individual(["a."], 3.0, False),
        Individual(["b."], 1.0, False),
    ]
    signatures = {individual.signature for individual in population}
    monkeypatch.setattr("gentians.evolution.replacements.oldest_or_worst.random.random", lambda: 1.0)

    updated = replace_oldest_or_worst(
        population,
        Individual(["c."], 2.0, False),
        signatures,
        0.0,
    )

    assert [individual.program for individual in updated] == [["a."], ["c."]]
    assert signatures == {updated[0].signature, updated[1].signature}


def test_replacement_keeps_population_sorted_when_replacing_oldest(monkeypatch):
    population = [
        Individual(["a."], 3.0, False),
        Individual(["b."], 2.0, False),
        Individual(["c."], 1.0, False),
    ]
    population[1].generated_timestamp = 0.0
    population[0].generated_timestamp = 1.0
    population[2].generated_timestamp = 2.0
    signatures = {individual.signature for individual in population}
    monkeypatch.setattr("gentians.evolution.replacements.oldest_or_worst.random.random", lambda: 0.0)

    updated = replace_oldest_or_worst(
        population,
        Individual(["d."], 2.5, False),
        signatures,
        1.0,
    )

    assert [individual.score for individual in updated] == [3.0, 2.5, 1.0]
    assert signatures == {updated[0].signature, updated[1].signature, updated[2].signature}


def test_program_sampler_generates_closed_program_from_forced_rules():
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

    closed = sampler.closed_program(2, forced_rules=[rules[0]])

    assert closed == sorted(rules)


def test_program_sampler_excludes_known_signature(monkeypatch):
    rules = ["target :- base.", "target :- alt."]
    program = Program(
        ["base.", "alt."],
        [Example(("target", ""), True)],
        [],
        [],
        [],
    )
    sampler = ProgramSampler(program, RuleSpace.from_clauses(rules))
    choices = iter(["target :- base.", "target :- alt."])
    monkeypatch.setattr("gentians.evolution.program_sampler.random.choice", lambda _: next(choices))

    sampled = sampler.closed_program(1, target_size=1, known_signatures={("target :- base.",)})

    assert sampled == ["target :- alt."]


def test_program_sampler_returns_none_when_dependency_cannot_close():
    rules = ["target :- missing."]
    program = Program(
        [],
        [Example(("target", ""), True)],
        [],
        [],
        [],
    )
    sampler = ProgramSampler(program, RuleSpace.from_clauses(rules))

    assert sampler.closed_program(1, forced_rules=rules) is None


def test_program_sampler_prunes_rules_with_unavailable_dependencies():
    rules = ["target :- base.", "target :- missing."]
    program = Program(
        ["base."],
        [Example(("target", ""), True)],
        [],
        [],
        [],
    )
    sampler = ProgramSampler(program, RuleSpace.from_clauses(rules))

    assert sampler.rule_space.clauses == ["target :- base."]


def test_program_sampler_respects_target_size_after_closure():
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

    assert sampler.closed_program(2, target_size=1) is None


def test_crossover_does_not_evaluate_unrepaired_sampler_child():
    parent_a = Individual(["a."], 1.0, False)
    parent_b = Individual(["b."], 2.0, False)

    class RejectingSampler:
        def closed_program(self, *args, **kwargs):
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
    parent_a = Individual(["a."], 1.0, False)
    parent_b = Individual(["b."], 2.0, False)
    metrics = []

    class ParentSampler:
        def closed_program(self, *args, **kwargs):
            return ["a."]

    monkeypatch.setattr(
        "gentians.evolution.crossovers.set_mix.record_metric",
        lambda kind, row: metrics.append(row),
    )
    monkeypatch.setattr(
        "gentians.evolution.crossovers.set_mix.metric_enabled",
        lambda kind: True,
    )

    set_mix_crossover(
        parent_a,
        parent_b,
        lambda program: (3.0, False),
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
        return 1.0, True

    population, best_found = initialize_population(
        1,
        5,
        score,
        _sampler(["a."]),
    )

    assert best_found is True
    assert len(population) == 1
    assert len(calls) == 1


def test_initialization_does_not_fallback_to_raw_when_sampler_fails():
    class RejectingSampler:
        def closed_program(self, *args, **kwargs):
            return None

    def fail_if_called(program):
        raise AssertionError("fitness should not run for raw fallback")

    with pytest.raises(RuntimeError, match="dependency-closed"):
        initialize_population(
            1,
            1,
            fail_if_called,
            RejectingSampler(),
        )


def test_initialization_accepts_partial_population_when_sampler_exhausts():
    class OneProgramSampler:
        def __init__(self):
            self.calls = 0

        def closed_program(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return ["a."]
            return None

    calls = []

    def score(program):
        calls.append(program)
        return 1.0, False

    population, best_found = initialize_population(
        1,
        5,
        score,
        OneProgramSampler(),
    )

    assert best_found is False
    assert [individual.program for individual in population] == [["a."]]
    assert calls == [["a."]]


def test_initialization_stops_retrying_duplicates_after_unique_attempts():
    class DuplicateSampler:
        def closed_program(self, *args, **kwargs):
            return ["a."]

    calls = []

    def score(program):
        calls.append(program)
        return 1.0, False

    population, best_found = initialize_population(
        1,
        2,
        score,
        DuplicateSampler(),
    )

    assert best_found is False
    assert [individual.program for individual in population] == [["a."]]
    assert calls == [["a."]]
