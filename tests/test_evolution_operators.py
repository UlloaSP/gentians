import random

import pytest

from gentians.arguments import Arguments
from gentians.evolution.algorithms import search
from gentians.evolution.algorithms.search import search_solver
from gentians.evolution.crossovers import create_crossover
from gentians.evolution.mutations import create_mutation
from gentians.evolution.populations import create_population
from gentians.evolution.selections import create_selection
from gentians.evolution.evolution_context import EvolutionContext
from gentians.evolution.individual import Individual
from gentians.evolution.operator_types import MutationProposal
from gentians.evolution.program_generators import ProgramGenerator
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


def test_structural_mutation_keeps_constraints_in_constraint_bucket():
    constraint = ":- q(V0)."
    neighbor = ":- q(V0),not blocked(V0)."
    context = _context(
        [constraint, neighbor, "target(V0) :- q(V0)."], max_clauses=1
    )
    mutation = create_mutation(
        {
            "name": "structural_neighbor",
            "probability": 1.0,
            "random_jump_probability": 0.0,
            "sample_size": 64,
        },
        context,
    )

    result = mutation(_encode(context, constraint), context)

    assert _render(context, result.program) == (neighbor,)
    assert result.local is True
    assert result.structural_distance == pytest.approx(0.5)


def test_structural_mutation_keeps_exact_rule_head():
    source = "target(V0) :- parent(V0)."
    same_head = "target(V0) :- mother(V0)."
    context = _context(
        [source, same_head, "other(V0) :- parent(V0)."], max_clauses=1
    )
    mutation = create_mutation(
        {
            "name": "structural_neighbor",
            "probability": 1.0,
            "random_jump_probability": 0.0,
        },
        context,
    )

    assert _render(context, mutation(_encode(context, source), context).program) == (
        same_head,
    )


def test_structural_head_bucket_includes_argument_topology():
    source = "target(V0,V0) :- parent(V0)."
    same_head = "target(V1,V1) :- mother(V1)."
    context = _context(
        [source, same_head, "target(V0,V1) :- parent(V0)."], max_clauses=1
    )
    mutation = create_mutation(
        {
            "name": "structural_neighbor",
            "probability": 1.0,
            "random_jump_probability": 0.0,
        },
        context,
    )

    assert _render(context, mutation(_encode(context, source), context).program) == (
        same_head,
    )


def test_structural_body_shape_stays_attached_to_canonical_head_variables():
    source = "target(X,Y) :- parent(X)."
    close = "target(A,B) :- parent(A)."
    far = "target(A,B) :- parent(B)."
    context = _context([source, far, close], max_clauses=1)
    mutation = create_mutation(
        {
            "name": "structural_neighbor",
            "probability": 1.0,
            "random_jump_probability": 0.0,
            "sample_size": 64,
        },
        context,
    )

    result = mutation(_encode(context, source), context)

    assert _render(context, result.program) == (close,)
    assert result.structural_distance == 0.0
    assert result.candidate_pool_size == 2


def test_structural_mutation_chooses_nearest_body_shape():
    source = ":- q(V0,V1),q(V2,V1),V0<V2."
    close = ":- q(V0,V1),q(V2,V1),V0>V2."
    far = ":- q(V0,V1),q(V2,V3),V1+V3=V2."
    context = _context([source, far, close], max_clauses=1)
    mutation = create_mutation(
        {
            "name": "structural_neighbor",
            "probability": 1.0,
            "random_jump_probability": 0.0,
            "sample_size": 64,
        },
        context,
    )

    result = mutation(_encode(context, source), context)

    assert _render(context, result.program) == (close,)
    assert result.structural_distance == pytest.approx(0.5)
    assert result.candidate_pool_size == 2


def test_structural_distance_is_invariant_to_variable_names():
    source = "target(X) :- parent(X,Y),parent(Y,Z)."
    renamed = "target(A) :- parent(B,C),parent(A,B)."
    context = _context([source, renamed], max_clauses=1)
    mutation = create_mutation(
        {
            "name": "structural_neighbor",
            "probability": 1.0,
            "random_jump_probability": 0.0,
        },
        context,
    )

    result = mutation(_encode(context, source), context)

    assert _render(context, result.program) == (renamed,)
    assert result.structural_distance == 0.0


def test_structural_distance_normalizes_named_underscore_variables():
    source = "target(_X) :- parent(_X)."
    renamed = "target(_Y) :- parent(_Y)."
    context = _context([source, renamed], max_clauses=1)
    mutation = create_mutation(
        {
            "name": "structural_neighbor",
            "probability": 1.0,
            "random_jump_probability": 0.0,
        },
        context,
    )

    assert mutation(_encode(context, source), context).structural_distance == 0.0


def test_structural_mutation_global_jump_can_change_head_class():
    source = "target(V0) :- parent(V0)."
    other = ":- parent(V0)."
    context = _context([source, other], max_clauses=1)
    mutation = create_mutation(
        {
            "name": "structural_neighbor",
            "probability": 1.0,
            "random_jump_probability": 1.0,
        },
        context,
    )

    result = mutation(_encode(context, source), context)

    assert _render(context, result.program) == (other,)
    assert result.local is False


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("random_jump_probability", 1.1, "between 0 and 1"),
        ("sample_size", 0, "at least 1"),
    ],
)
def test_structural_mutation_validates_config(key, value, message):
    context = _context(["a.", "b."], max_clauses=1)
    config = {"name": "structural_neighbor", "probability": 1.0, key: value}

    with pytest.raises(ValueError, match=message):
        create_mutation(config, context)


def test_structural_mutation_rejects_rules_above_supported_variable_bound():
    context = _context(
        [
            "target(V0) :- rel(V0,V1,V2,V3,V4,V5,V6).",
            "target(V0) :- other(V0).",
        ],
        max_clauses=1,
    )

    mutation = create_mutation(
        {"name": "structural_neighbor", "probability": 1.0}, context
    )
    with pytest.raises(ValueError, match="at most 6 variables"):
        mutation(_encode(context, context.space.clauses[0]), context)


def test_mutation_metrics_include_structural_and_program_distances(monkeypatch):
    rows = []
    monkeypatch.setattr(search, "record_metric", lambda _kind, row: rows.append(row))
    parent = Individual(0b011, 1.0, False)
    child = Individual(0b101, 2.0, False)
    proposal = MutationProposal(
        child.program,
        operation="replace",
        local=True,
        structural_distance=0.25,
        candidate_pool_size=12,
    )

    search._mutation_metric(
        {"name": "structural_neighbor"},
        parent,
        child,
        proposal,
        duplicate=False,
    )

    [row] = rows
    assert row["operation"] == "replace"
    assert row["local"] is True
    assert row["structural_distance"] == 0.25
    assert row["candidate_pool_size"] == 12
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
                "tournament_size": 3,
                "prob_selecting_fittest": 1.0,
            }
        )
    except ValueError as error:
        assert "Unknown selection strategy" in str(error)
    else:
        raise AssertionError("legacy tournament alias was accepted")


def test_program_generator_creates_only_closed_programs():
    rules = (
        "heads(V0):- coin(V0),not tails(V0).",
        "tails(V0):- coin(V0),not heads(V0).",
    )
    program = Program(["coin(c1)."], [], [], [], [])
    space = RuleSpace.from_clauses(list(rules))
    generator = ProgramGenerator(
        program, space, 2, random.Random(1), fixed_size=True
    )

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
    generator = ProgramGenerator(
        program, space, 3, random.Random(1), fixed_size=True
    )

    [generated] = generator.create_population(1)

    assert generated is not None
    rendered = generator.render(generated)
    assert generated.bit_count() == 3
    assert consumer in rendered
    assert mother in rendered or father in rendered


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


def test_fixed_size_generator_keeps_every_transition_at_target_size():
    program = Program([], [], [], [], [])
    space = RuleSpace.from_clauses(["a.", "b.", "c.", "d."])
    generator = ProgramGenerator(
        program, space, 3, random.Random(1), fixed_size=True
    )
    [generated] = generator.create_population(1)

    assert generated is not None
    assert generated.bit_count() == 3
    assert generator.mutate_random(generated).program.bit_count() == 3


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
    results = iter((None, proposal))
    monkeypatch.setattr(generator, "_complete", lambda _proposal, _forbidden: next(results))

    assert generator._build(proposal, 0) is None
    assert generator._build(proposal, 0) == proposal


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

        def mutate_structural(self, program, jump_probability, sample_size):
            self.calls.append(
                ("structural", program, jump_probability, sample_size)
            )
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
    create_mutation(
        {
            "name": "structural_neighbor",
            "probability": 1.0,
            "random_jump_probability": 0.2,
            "sample_size": 5,
        },
        context,
    )(genome, context)
    create_crossover({"name": "set_mix", "probability": 1.0})(
        genome, 2, context
    )

    assert [call[0] for call in generator.calls] == [
        "population",
        "random",
        "structural",
        "crossover",
    ]


def test_single_engine_accepts_supplied_hypothesis_space(monkeypatch):
    args = Arguments(
        max_program_clauses=1,
        random_seed=3,
        iterations_genetic=0,
        population={"name": "random", "size": 1},
    )
    monkeypatch.setattr(
        "gentians.evolution.algorithms.search.create_fitness",
        lambda program, config, max_program_clauses, rule_space: lambda candidate: (
            1.0,
            True,
        ),
    )
    result, score, best = search_solver(
        args,
        Program([], [], [], [], []),
        RuleSpace.from_clauses(["good."]),
    )
    assert result == ("good.",)
    assert score == 1.0
    assert best is True


def test_mutation_runs_when_crossover_is_skipped(monkeypatch):
    args = Arguments(
        max_program_clauses=1,
        random_seed=3,
        iterations_genetic=1,
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
            lambda candidate: (
                1.0 if candidate == ("win.",) else 0.0,
                candidate == ("win.",),
            )
        ),
    )

    result, score, best = search_solver(
        args,
        Program([], [], [], [], []),
        RuleSpace.from_clauses(["start.", "win."]),
    )

    assert result == ("win.",)
    assert score == 1.0
    assert best is True


def test_repeated_crossover_child_is_recorded_as_duplicate(monkeypatch):
    rows = []
    args = Arguments(
        max_program_clauses=1,
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
            lambda candidate: (1.0, False)
        ),
    )
    monkeypatch.setattr(search, "record_metric", lambda _kind, row: rows.append(row))

    search_solver(
        args,
        Program([], [], [], [], []),
        RuleSpace.from_clauses(["start.", "cross."]),
    )

    crossover_rows = [row for row in rows if row["operator"] == "crossover"]
    assert [row["duplicate"] for row in crossover_rows] == [False, True]
