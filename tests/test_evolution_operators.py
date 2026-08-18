import random

import pytest

from gentians.arguments import Arguments
from gentians.evolution.algorithms import search
from gentians.evolution.algorithms.search import search_solver
from gentians.evolution.crossovers import create_crossover
from gentians.evolution.mutations import create_mutation
from gentians.evolution.populations import create_population
from gentians.evolution.selections import create_selection
from gentians.evolution.selections.behavior_tournament_selection import (
    BehaviorTournamentSelection,
)
from gentians.evolution.selections.tournament_selection import TournamentSelection
from gentians.evolution.evolution_context import EvolutionContext
from gentians.evolution.individual import Individual
from gentians.evolution.operator_types import MutationProposal
from gentians.evolution.program_generators import ProgramGenerator
from gentians.evolution.replacements.oldest_or_worst import OldestOrWorstReplacement
from gentians.evolution.types import FitnessResult
from gentians.rule_generation.program import Program
from gentians.rule_generation.example import Example
from gentians.rule_generation.rule_space import RuleSpace


def _context(rules, *, max_clauses=3):
    space = RuleSpace.from_clauses(list(rules))
    dependencies = set().union(*(entry.deps for entry in space.entries), set())
    background = [
        f"{name}({','.join('c' for _ in range(arity))})." if arity else f"{name}."
        for name, arity in sorted(dependencies)
    ]
    program = Program(background, [], [], [], [])
    rng = random.Random(7)
    program_generator = ProgramGenerator(program, space, max_clauses, rng)
    return EvolutionContext(
        program_generator.space, program_generator, max_clauses, rng
    )


def _encode(context, *rules):
    return context.generator.encode(tuple(rules))


def _render(context, genome):
    return context.generator.render(genome)


def test_all_mutations_share_genome_contract():
    context = _context(["a.", "b.", "c."])
    genome = _encode(context, "a.", "b.")
    result = create_mutation(
        {"name": "random_group", "probability": 1.0}, context
    )(
        genome, context
    )
    assert isinstance(result.program, int)
    assert set(_render(context, result.program)) <= set(context.space.clauses)


def test_structural_neighbor_replaces_with_same_head():
    source = "target(X,Y) :- parent(X)."
    same_head = "target(A,B) :- parent(B)."
    other_head = "other(A,B) :- parent(B)."
    context = _context([source, same_head, other_head], max_clauses=1)
    mutation = create_mutation(
        {
            "name": "structural_neighbor",
            "probability": 1.0,
            "random_jump_probability": 0.0,
        },
        context,
    )

    result = mutation(_encode(context, source), context)

    assert _render(context, result.program) == (same_head,)
    assert result.local is True


def test_structural_neighbor_does_not_materialize_available_rules(monkeypatch):
    source = "target(X,Y) :- parent(X)."
    same_head = "target(A,B) :- parent(B)."
    context = _context([source, same_head, "other(X) :- parent(X)."], max_clauses=1)
    program = _encode(context, source)
    random_ids = context.generator._random_ids

    def only_program_ids(mask):
        assert mask == program
        return random_ids(mask)

    monkeypatch.setattr(context.generator, "_random_ids", only_program_ids)
    mutation = create_mutation(
        {
            "name": "structural_neighbor",
            "probability": 1.0,
            "random_jump_probability": 0.0,
        },
        context,
    )

    result = mutation(program, context)

    assert _render(context, result.program) == (same_head,)


def test_structural_neighbor_random_jump_can_change_head():
    source = "target(X) :- parent(X)."
    other_head = "other(X) :- parent(X)."
    context = _context([source, other_head], max_clauses=1)
    mutation = create_mutation(
        {
            "name": "structural_neighbor",
            "probability": 1.0,
            "random_jump_probability": 1.0,
        },
        context,
    )

    result = mutation(_encode(context, source), context)

    assert _render(context, result.program) == (other_head,)
    assert result.local is False


def test_mutation_metrics_include_local_and_program_distance(monkeypatch):
    rows = []
    monkeypatch.setattr(search, "record_metric", lambda _kind, row: rows.append(row))
    parent = Individual(0b011, 1.0, False)
    child = Individual(0b101, 2.0, False)
    proposal = MutationProposal(
        child.program,
        operation="replace",
        local=True,
    )

    search._mutation_metric(
        {"name": "structural_neighbor"},
        parent.program,
        parent,
        child,
        proposal,
        duplicate=False,
        crossover_strategy="set_mix",
        crossover_improved=False,
        lost_crossover_gain=False,
    )

    [row] = rows
    assert row["operation"] == "replace"
    assert row["local"] is True
    assert row["program_distance"] == pytest.approx(2 / 3)
    assert row["changed_rules"] == 2
    assert row["valid_new"] is True


def test_all_crossovers_share_genome_contract():
    context = _context(["a.", "b.", "c."])
    children = create_crossover({"name": "set_mix", "probability": 1.0})(
        _encode(context, "a.", "b."), _encode(context, "b.", "c."), context
    )
    assert isinstance(children, tuple)
    assert all(isinstance(child, int) for child in children)


def test_crossover_generates_closed_programs_directly():
    consumer = "heads(V0) :- coin(V0),not tails(V0)."
    first_provider = "tails(V0) :- coin(V0)."
    second_provider = "tails(V0) :- marked(V0)."
    program = Program(["coin(c1).", "marked(c1)."], [], [], [], [])
    space = RuleSpace.from_clauses(
        [consumer, first_provider, second_provider]
    )
    rng = random.Random(3)
    generator = ProgramGenerator(program, space, 2, rng)
    context = EvolutionContext(generator.space, generator, 2, rng)

    children = create_crossover({"name": "set_mix", "probability": 1.0})(
        generator.encode(tuple(sorted((consumer, first_provider)))),
        generator.encode(tuple(sorted((consumer, second_provider)))),
        context,
    )

    assert children
    rendered = [generator.render(child) for child in children]
    assert all(consumer in child for child in rendered)
    assert all(
        first_provider in child or second_provider in child for child in rendered
    )
    assert all(child.bit_count() == 2 for child in children)


def test_tournament_has_one_canonical_strategy_name():
    try:
        create_selection(
            {
                "name": "original_tournament",
                "tournament_percentage": 0.3,
                "prob_selecting_fittest": 1.0,
            }
        )
    except ValueError as error:
        assert "Unknown selection strategy" in str(error)
    else:
        raise AssertionError("legacy tournament alias was accepted")


def test_tournament_size_scales_with_population_percentage():
    sampled_sizes = []

    class RecordingRandom(random.Random):
        def sample(self, population, k, *, counts=None):
            sampled_sizes.append(k)
            return super().sample(population, k, counts=counts)

    selection = TournamentSelection(0.3, 1.0)
    rng = RecordingRandom(1)

    selection([Individual(index, float(index), False) for index in range(10)], rng)
    selection([Individual(index, float(index), False) for index in range(100)], rng)

    assert sampled_sizes == [3, 3, 30, 30]


def test_behavior_tournament_chooses_most_complete_parent_regardless_of_score():
    selection = BehaviorTournamentSelection(1.0)
    high_score = Individual(1, 10.0, False, behavior=(0b0011, 0))
    most_complete = Individual(2, 1.0, False, behavior=(0b1111, 0b11))
    other = Individual(4, 9.0, False, behavior=(0b0001, 0b1))

    first, _ = selection([high_score, most_complete, other], random.Random(1))

    assert first is most_complete


def test_behavior_tournament_factory_creates_strategy():
    selection = create_selection(
        {
            "name": "behavior_tournament",
            "tournament_percentage": 0.3,
        }
    )

    assert isinstance(selection, BehaviorTournamentSelection)
    assert selection.percentage == 0.3


def test_behavior_tournament_chooses_most_consistent_second_parent():
    selection = BehaviorTournamentSelection(1.0)
    first = Individual(1, 1.0, False, behavior=(0b1111, 0b11))
    unsafe = Individual(2, 10.0, False, behavior=(0b111, 0b1))
    consistent = Individual(4, 0.0, False, behavior=(0b001, 0))

    parents = selection([first, unsafe, consistent], random.Random(1))

    assert parents == (first, consistent)


def test_behavior_tournament_reuses_only_parent_in_singleton_population():
    selection = BehaviorTournamentSelection(1.0)
    only = Individual(1, 1.0, False, behavior=(1, 0))

    assert selection([only], random.Random(1)) == (only, only)


def test_behavior_tournament_compares_at_least_two_mates():
    sampled_sizes = []

    class RecordingRandom(random.Random):
        def sample(self, population, k, *, counts=None):
            sampled_sizes.append(k)
            return super().sample(population, k, counts=counts)

    population = [
        Individual(index, float(index), False, behavior=(index, 0))
        for index in range(10)
    ]

    BehaviorTournamentSelection(0.1)(population, RecordingRandom(1))

    assert sampled_sizes == [2]


@pytest.mark.parametrize("percentage", [0.0, -0.1, 1.1])
def test_tournament_percentage_rejects_out_of_range_values(percentage):
    with pytest.raises(ValueError, match="tournament_percentage"):
        TournamentSelection(percentage, 1.0)


def test_program_generator_creates_only_closed_programs():
    rules = (
        "heads(V0):- coin(V0),not tails(V0).",
        "tails(V0):- coin(V0),not heads(V0).",
    )
    program = Program(["coin(c1)."], [], [], [], [])
    space = RuleSpace.from_clauses(list(rules))
    generator = ProgramGenerator(program, space, 2, random.Random(1))

    assert [generator.render(genome) for genome in generator.create_population(1)] == [
        tuple(sorted(rules))
    ]


def test_program_generator_builds_invented_definition_module():
    consumer = "target(V0,V2) :- helper(V0,V1),helper(V1,V2)."
    mother = "helper(V0,V1) :- mother(V0,V1)."
    father = "helper(V0,V1) :- father(V0,V1)."
    recursive = "helper(V1,V0) :- helper(V0,V1)."
    constraint = ":- helper(V0,V1),bad(V0)."
    program = Program(
        ["mother(a,b).", "father(b,c).", "bad(d)."],
        [Example(("target(a,c)", ""), True)],
        [],
        [],
        [],
        invented_predicates=(("helper", 2),),
    )
    space = RuleSpace.from_clauses(
        [consumer, mother, father, recursive, constraint]
    )
    generator = ProgramGenerator(program, space, 3, random.Random(1))
    generator.rng.randint = lambda _start, end: end

    [generated] = generator.create_population(1)

    assert generated is not None
    rendered = generator.render(generated)
    assert generated.bit_count() == 3
    assert consumer in rendered
    assert mother in rendered or father in rendered


def test_population_accepts_closure_larger_than_sampled_size(monkeypatch):
    consumer = "target(V0) :- helper(V0)."
    provider = "helper(V0) :- base(V0)."
    program = Program(
        ["base(a)."],
        [Example(("target(a)", ""), True)],
        [],
        [],
        [],
        invented_predicates=(("helper", 1),),
    )
    generator = ProgramGenerator(
        program,
        RuleSpace.from_clauses([consumer, provider]),
        2,
        random.Random(1),
    )
    monkeypatch.setattr(generator.rng, "randint", lambda _start, _end: 1)

    [generated] = generator.create_population(1)

    assert generator.render(generated) == tuple(sorted((consumer, provider)))


def test_program_generator_applies_mutation_atomically():
    seed = "seed(V0) :- coin(V0)."
    consumer = "heads(V0) :- coin(V0),not tails(V0)."
    provider = "tails(V0) :- coin(V0)."
    alternative = "tails(V0) :- marked(V0)."
    program = Program(["coin(c1).", "marked(c1)."], [], [], [], [])
    generator = ProgramGenerator(
        program,
        RuleSpace.from_clauses([seed, consumer, provider, alternative]),
        3,
        random.Random(1),
    )

    result = generator.mutate_random(generator.encode((seed, consumer, provider)))

    rendered = generator.render(result.program)
    assert rendered != tuple(sorted((seed, consumer, provider)))
    assert consumer not in rendered or provider in rendered or alternative in rendered


def test_generator_prunes_uncloseable_rules():
    program = Program(["base."], [], [], [], [])
    space = RuleSpace.from_clauses(["base.", "target :- missing."])
    generator = ProgramGenerator(program, space, 2, random.Random(1))

    assert generator.space.clauses == ("base.",)
    assert [generator.render(genome) for genome in generator.create_population(2)] == [
        ("base.",)
    ]


def test_program_generator_creates_requested_population_size():
    program = Program([], [], [], [], [])
    space = RuleSpace.from_clauses(["a.", "b.", "c."])
    generator = ProgramGenerator(program, space, 3, random.Random(1))

    assert len(generator.create_population(3)) == 3


def test_program_generator_uses_canonical_bitset_genomes():
    generator = ProgramGenerator(
        Program([], [], [], [], []),
        RuleSpace.from_clauses(["a.", "b.", "c.", "d."]),
        3,
        random.Random(1),
    )

    genome = generator.encode(("c.", "a.", "c."))
    available = list(generator._random_available(genome))

    assert isinstance(genome, int)
    assert genome.bit_count() == 2
    assert generator.render(genome) == ("a.", "c.")
    assert sorted(available) == [generator.rule_ids["b."], generator.rule_ids["d."]]


def test_program_generator_does_not_cache_bounded_search_failures(monkeypatch):
    generator = ProgramGenerator(
        Program([], [], [], [], []),
        RuleSpace.from_clauses(["a."]),
        1,
        random.Random(1),
    )
    proposal = generator.encode(("a.",))
    calls = 0

    def fail(_proposal, _forbidden):
        nonlocal calls
        calls += 1
        return None

    monkeypatch.setattr(generator, "_complete", fail)

    assert generator._build(proposal, 0) is None
    assert generator._build(proposal, 0) is None
    assert calls == 2


def test_program_generator_records_one_closure_per_public_transition(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "gentians.evolution.program_generators.common.add",
        lambda name, seconds: calls.append((name, seconds)),
    )
    generator = ProgramGenerator(
        Program([], [], [], [], []),
        RuleSpace.from_clauses(["a.", "b.", "c."]),
        2,
        random.Random(1),
    )

    generator.create_population(2)
    generator.mutate_random(generator.encode(("a.",)))
    generator.mix(
        generator.encode(("a.",)),
        generator.encode(("b.",)),
        ((0.7, 0.3), (0.3, 0.7)),
    )

    assert len(calls) == 3
    assert all(name.endswith(".closure") for name, _seconds in calls)


def test_generation_consumers_make_one_high_level_generator_call():
    class GeneratorSpy:
        def __init__(self):
            self.calls = []

        def create_population(self, size):
            self.calls.append(("population", size))
            return []

        def mutate_random(self, program):
            self.calls.append(("random", program))
            return MutationProposal(program)

        def mix(self, first, second, probabilities):
            self.calls.append(("crossover", first, second, probabilities))
            return ()

    generator = GeneratorSpy()
    space = RuleSpace.from_clauses(["a.", "b."])
    context = EvolutionContext(space, generator, 2, random.Random(1))
    genome = 1

    create_population({"name": "random", "size": 3})(context)
    create_mutation({"name": "random_group", "probability": 1.0}, context)(
        genome, context
    )
    create_crossover({"name": "set_mix", "probability": 1.0})(
        genome, 2, context
    )

    assert [call[0] for call in generator.calls] == [
        "population",
        "random",
        "crossover",
    ]


def test_single_engine_accepts_supplied_hypothesis_space(monkeypatch):
    generations = []
    args = Arguments(
        random_seed=3,
        iterations_genetic=0,
        population={"name": "random", "size": 2},
    )
    monkeypatch.setattr(
        search,
        "create_population",
        lambda config: lambda context: [
            context.generator.encode(("good.",)),
            context.generator.encode(("higher-score.",)),
        ],
    )
    monkeypatch.setattr(
        "gentians.evolution.algorithms.search.create_fitness",
        lambda program, config, max_program_clauses, rule_space: lambda candidate: FitnessResult(
            1.0 if candidate == ("good.",) else 2.0,
            candidate == ("good.",),
            candidate,
            (1, 0) if candidate == ("good.",) else (0, 0),
        ),
    )
    monkeypatch.setattr(
        search,
        "record_ga_generation",
        lambda generation, best_so_far, population, **kwargs: generations.append(
            (generation, best_so_far, [item.score for item in population])
        ),
    )
    result, score, best = search_solver(
        args,
        Program([], [], [], [], [], max_program_clauses=1),
        RuleSpace.from_clauses(["good.", "higher-score."]),
    )
    assert result == ("good.",)
    assert score == 1.0
    assert best is True
    assert generations == [(0, 2.0, [2.0, 1.0])]


def test_default_unlimited_generations_run_until_winner(monkeypatch):
    generations = []
    args = Arguments(
        random_seed=3,
        population={"name": "random", "size": 1},
        crossover={"name": "set_mix", "probability": 0.0},
        mutation={"name": "random_group", "probability": 1.0},
    )
    monkeypatch.setattr(
        search,
        "create_population",
        lambda config: lambda context: [context.generator.encode(("start.",))],
    )
    monkeypatch.setattr(
        search,
        "create_mutation",
        lambda config, context: lambda genome, context: MutationProposal(
            context.generator.encode(("win.",))
        ),
    )
    monkeypatch.setattr(
        search,
        "create_fitness",
        lambda program, config, max_program_clauses, rule_space: (
            lambda candidate: FitnessResult(
                1.0 if candidate == ("win.",) else 0.0,
                candidate == ("win.",),
                candidate,
                (1, 0) if candidate == ("win.",) else (0, 0),
            )
        ),
    )

    monkeypatch.setattr(
        search,
        "record_ga_generation",
        lambda generation, best_so_far, population, **kwargs: generations.append(
            (generation, best_so_far, [item.score for item in population])
        ),
    )

    result, score, best = search_solver(
        args,
        Program([], [], [], [], [], max_program_clauses=1),
        RuleSpace.from_clauses(["start.", "win."]),
    )

    assert result == ("win.",)
    assert score == 1.0
    assert best is True
    assert generations == [(0, 0.0, [0.0]), (1, 1.0, [1.0])]


def test_winning_crossover_child_is_evaluated_before_mutation(monkeypatch):
    mutation_calls = []
    generations = []
    args = Arguments(
        random_seed=3,
        iterations_genetic=1,
        population={"name": "random", "size": 2},
    )
    monkeypatch.setattr(
        search,
        "create_population",
        lambda config: lambda context: [
            context.generator.encode(("start.",)),
            context.generator.encode(("loss.",)),
        ],
    )
    monkeypatch.setattr(
        search,
        "create_crossover",
        lambda config: lambda first, second, context: (
            context.generator.encode(("win.",)),
        ),
    )

    def destructive_mutation(genome, context):
        mutation_calls.append(genome)
        return MutationProposal(context.generator.encode(("loss.",)))

    monkeypatch.setattr(
        search,
        "create_mutation",
        lambda config, context: destructive_mutation,
    )
    monkeypatch.setattr(
        search,
        "create_fitness",
        lambda program, config, max_program_clauses, rule_space: (
            lambda candidate: FitnessResult(
                -1.0 if candidate == ("win.",) else 0.0,
                candidate == ("win.",),
                candidate,
                (1, 0) if candidate == ("win.",) else (0, 0),
            )
        ),
    )

    monkeypatch.setattr(
        search,
        "record_ga_generation",
        lambda generation, best_so_far, population, **kwargs: generations.append(
            (generation, best_so_far, [item.score for item in population])
        ),
    )
    result, score, best = search_solver(
        args,
        Program([], [], [], [], []),
        RuleSpace.from_clauses(["start.", "win.", "loss."]),
    )

    assert result == ("win.",)
    assert score == -1.0
    assert best is True
    assert mutation_calls == []
    assert generations == [(0, 0.0, [0.0, 0.0]), (1, 0.0, [0.0, -1.0])]


def test_destructive_mutation_records_lost_crossover_gain(monkeypatch):
    rows = []
    args = Arguments(
        random_seed=3,
        iterations_genetic=1,
        population={"name": "random", "size": 2},
    )
    monkeypatch.setattr(
        search,
        "create_population",
        lambda config: lambda context: [
            context.generator.encode(("start.",)),
            context.generator.encode(("other.",)),
        ],
    )
    monkeypatch.setattr(
        search,
        "create_crossover",
        lambda config: lambda first, second, context: (
            context.generator.encode(("cross.",)),
        ),
    )
    monkeypatch.setattr(
        search,
        "create_mutation",
        lambda config, context: lambda genome, context: MutationProposal(
            context.generator.encode(("mutated.",))
        ),
    )
    scores = {"start.": 1.0, "other.": 0.0, "cross.": 2.0, "mutated.": 1.5}
    monkeypatch.setattr(
        search,
        "create_fitness",
        lambda program, config, max_program_clauses, rule_space: (
            lambda candidate: FitnessResult(scores[candidate[0]], False, candidate, (0, 0))
        ),
    )
    monkeypatch.setattr(search, "record_metric", lambda _kind, row: rows.append(row))

    search_solver(
        args,
        Program([], [], [], [], [], max_program_clauses=1),
        RuleSpace.from_clauses(["start.", "other.", "cross.", "mutated."]),
    )

    [mutation] = [row for row in rows if row["operator"] == "mutation"]
    assert mutation["crossover_strategy"] == "set_mix"
    assert mutation["crossover_improved"] is True
    assert mutation["lost_crossover_gain"] is True


def test_repeated_crossover_child_is_recorded_as_duplicate(monkeypatch):
    rows = []
    args = Arguments(
        random_seed=3,
        iterations_genetic=1,
        population={"name": "random", "size": 1},
        mutation={"name": "random_group", "probability": 0.0},
    )
    monkeypatch.setattr(
        search,
        "create_population",
        lambda config: lambda context: [context.generator.encode(("start.",))],
    )
    monkeypatch.setattr(
        search,
        "create_crossover",
        lambda config: lambda first, second, context: (
            context.generator.encode(("cross.",)),
            context.generator.encode(("cross.",)),
        ),
    )
    monkeypatch.setattr(
        search,
        "create_fitness",
        lambda program, config, max_program_clauses, rule_space: (
            lambda candidate: FitnessResult(1.0, False, candidate, (0, 0))
        ),
    )
    monkeypatch.setattr(search, "record_metric", lambda _kind, row: rows.append(row))

    search_solver(
        args,
        Program([], [], [], [], [], max_program_clauses=1),
        RuleSpace.from_clauses(["start.", "cross."]),
    )

    crossover_rows = [row for row in rows if row["operator"] == "crossover"]
    assert [row["duplicate"] for row in crossover_rows] == [False, True]


@pytest.mark.parametrize("mutation_name", ["random_group", "structural_neighbor"])
def test_probability_skipped_mutation_is_not_recorded_as_duplicate(
    monkeypatch, mutation_name
):
    rows = []
    args = Arguments(
        random_seed=3,
        iterations_genetic=1,
        population={"name": "random", "size": 1},
        crossover={"name": "set_mix", "probability": 0.0},
        mutation={"name": mutation_name, "probability": 0.0},
    )
    monkeypatch.setattr(
        search,
        "create_population",
        lambda config: lambda context: [context.generator.encode(("start.",))],
    )
    monkeypatch.setattr(
        search,
        "create_fitness",
        lambda program, config, max_program_clauses, rule_space: (
            lambda candidate: FitnessResult(1.0, False, candidate, (0, 0))
        ),
    )
    monkeypatch.setattr(search, "record_metric", lambda _kind, row: rows.append(row))

    search_solver(
        args,
        Program([], [], [], [], [], max_program_clauses=1),
        RuleSpace.from_clauses(["start.", "other."]),
    )

    mutation_rows = [row for row in rows if row["operator"] == "mutation"]
    assert mutation_rows
    assert all(row["skipped"] is True for row in mutation_rows)
    assert all(row["duplicate"] is False for row in mutation_rows)


def test_equal_novel_candidate_replaces_an_existing_individual():
    population = [
        Individual(1, 0.0, False, generated_timestamp=1.0),
        Individual(2, 0.0, False, generated_timestamp=2.0),
    ]
    candidate = Individual(4, 0.0, False, generated_timestamp=3.0)

    result = OldestOrWorstReplacement(0.0)(population, candidate, random.Random(1))

    assert candidate in result
    assert len(result) == len(population)


def test_equal_score_new_behavior_evicts_repeated_behavior():
    population = [
        Individual(1, 2.0, False, behavior=(1, 1), generated_timestamp=1.0),
        Individual(2, 2.0, False, behavior=(1, 1), generated_timestamp=2.0),
        Individual(4, 2.0, False, behavior=(2, 1), generated_timestamp=3.0),
    ]
    candidate = Individual(
        8, 2.0, False, behavior=(2, 0), generated_timestamp=4.0
    )

    result = OldestOrWorstReplacement(0.0, behavior_tiebreak=True)(
        population, candidate, random.Random(1)
    )

    assert candidate in result
    assert Individual(1, 2.0, False, behavior=(1, 1), generated_timestamp=1.0) not in result
    assert {item.behavior for item in result} == {(1, 1), (2, 1), (2, 0)}
