import random

import pytest

from gentians.arguments import Arguments
from gentians.algorithms import steady_state_genetic_search
from gentians.algorithms import steady_state_genetic as search
from gentians.evolution import metrics as evolution_metrics
from gentians.evolution.crossovers import create_crossover
from gentians.evolution.context import EvolutionContext
from gentians.evolution.individual import Individual
from gentians.evolution.mutations import create_mutation
from gentians.evolution.operator_types import MutationProposal
from gentians.evolution.populations import create_population
from gentians.hypotheses import HypothesisGenerator
from gentians.evolution.replacements.oldest_or_worst import OldestOrWorstReplacement
from gentians.evolution.selections import create_selection
from gentians.evolution.selections.behavior_tournament_selection import (
    BehaviorTournamentSelection,
)
from gentians.evolution.selections.lexicase_selection import LexicaseSelection
from gentians.evolution.selections.tournament_selection import TournamentSelection
from gentians.evaluation.result import EvaluationResult
from tests.task_helpers import example, inductive_task, make_clause_space


def _context(rules, *, max_clauses=3):
    space = make_clause_space(list(rules))
    dependencies = set().union(*(entry.deps for entry in space.entries), set())
    background = [
        f"{name}({','.join('c' for _ in range(arity))})." if arity else f"{name}."
        for name, arity in sorted(dependencies)
    ]
    program = inductive_task(background, [], [], [], [])
    rng = random.Random(7)
    hypothesis_generator = HypothesisGenerator(program, space, max_clauses)
    return EvolutionContext(hypothesis_generator, rng)


@pytest.mark.parametrize(
    ("factory", "config"),
    [
        (create_crossover, {"name": "set_mix", "probability": 1.1}),
        (create_crossover, {"name": "set_mix", "probability": True}),
        (create_crossover, {"name": "set_mix", "probability": "0.5"}),
        (create_mutation, {"name": "random_group", "probability": -0.1}),
        (
            create_mutation,
            {
                "name": "structural_neighbor",
                "probability": 0.5,
                "random_jump_probability": True,
            },
        ),
        (
            create_selection,
            {
                "name": "tournament",
                "tournament_percentage": 0.5,
                "prob_selecting_fittest": 1.1,
            },
        ),
        (create_population, {"name": "random", "size": 0}),
        (create_population, {"name": "random", "size": 1.5}),
    ],
)
def test_operator_factories_reject_invalid_configuration(factory, config):
    with pytest.raises(ValueError):
        factory(config)


def test_crossover_is_enabled_by_default():
    assert Arguments().crossover["probability"] == 1.0


def test_unknown_mutation_is_reported_before_strategy_parameters():
    with pytest.raises(ValueError, match="Unknown mutation strategy: unknown"):
        create_mutation({"name": "unknown"})


def _encode(context, *rules):
    return context.hypotheses.encode(tuple(rules))


def _render(context, genome):
    return context.hypotheses.render(genome)


def _population(generator, size, rng=None):
    context = EvolutionContext(generator, rng or random.Random(1))
    return create_population({"name": "random", "size": size})(context)


def test_all_mutations_share_genome_contract():
    context = _context(["a.", "b.", "c."])
    genome = _encode(context, "a.", "b.")
    result = create_mutation({"name": "random_group", "probability": 1.0})(
        genome, context
    )
    assert isinstance(result.genome, int)
    assert set(_render(context, result.genome)) <= set(context.hypotheses.space.clauses)


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
    )

    result = mutation(_encode(context, source), context)

    assert _render(context, result.genome) == (same_head,)
    assert result.local is True


def test_structural_neighbor_does_not_materialize_available_rules(monkeypatch):
    source = "target(X,Y) :- parent(X)."
    same_head = "target(A,B) :- parent(B)."
    context = _context([source, same_head, "other(X) :- parent(X)."], max_clauses=1)
    program = _encode(context, source)
    random_ids = context.hypotheses._random_ids

    def only_program_ids(mask, rng):
        assert mask == program
        return random_ids(mask, rng)

    monkeypatch.setattr(context.hypotheses, "_random_ids", only_program_ids)
    mutation = create_mutation(
        {
            "name": "structural_neighbor",
            "probability": 1.0,
            "random_jump_probability": 0.0,
        },
    )

    result = mutation(program, context)

    assert _render(context, result.genome) == (same_head,)


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
    )

    result = mutation(_encode(context, source), context)

    assert _render(context, result.genome) == (other_head,)
    assert result.local is False


def test_mutation_metrics_include_local_and_program_distance(monkeypatch):
    rows = []
    monkeypatch.setenv("GENTIANS_OPERATOR_METRICS_PATH", "metrics.jsonl")
    monkeypatch.setattr(
        evolution_metrics, "record_metric", lambda _kind, row: rows.append(row)
    )
    parent = Individual(0b011, 1.0, False)
    child = Individual(0b101, 2.0, False)
    proposal = MutationProposal(
        child.genome,
        operation="replace",
        local=True,
    )

    evolution_metrics.record_mutation(
        "structural_neighbor",
        parent.genome,
        proposal,
        duplicate=False,
    )

    [row] = rows
    assert row["operation"] == "replace"
    assert row["local"] is True
    assert row["program_distance"] == pytest.approx(2 / 3)
    assert row["changed_rules"] == 2
    assert row["valid_new"] is True


def test_disabled_operator_metrics_skip_payload_work(monkeypatch):
    monkeypatch.delenv("GENTIANS_OPERATOR_METRICS_PATH", raising=False)
    monkeypatch.setattr(
        evolution_metrics,
        "_program_distance",
        lambda *_args: pytest.fail("disabled metrics built a payload"),
    )

    evolution_metrics.record_mutation(
        "random_group",
        0b01,
        MutationProposal(0b10),
        duplicate=False,
    )


def test_all_crossovers_share_genome_contract():
    context = _context(["a.", "b.", "c."])
    child = create_crossover({"name": "set_mix", "probability": 1.0})(
        _encode(context, "a.", "b."), _encode(context, "b.", "c."), context
    )
    assert isinstance(child, int)


def test_crossover_generates_closed_programs_directly():
    consumer = "heads(V0) :- coin(V0),not tails(V0)."
    first_provider = "tails(V0) :- coin(V0)."
    second_provider = "tails(V0) :- marked(V0)."
    program = inductive_task(["coin(c1).", "marked(c1)."], [], [], [], [])
    space = make_clause_space([consumer, first_provider, second_provider])
    rng = random.Random(3)
    generator = HypothesisGenerator(program, space, 2)
    context = EvolutionContext(generator, rng)

    child = create_crossover({"name": "set_mix", "probability": 1.0})(
        generator.encode(tuple(sorted((consumer, first_provider)))),
        generator.encode(tuple(sorted((consumer, second_provider)))),
        context,
    )

    assert child is not None
    rendered = generator.render(child)
    assert consumer in rendered
    assert first_provider in rendered or second_provider in rendered
    assert child.bit_count() == 2


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


def test_lexicase_filters_by_individual_positive_examples():
    class OrderedRandom(random.Random):
        def shuffle(self, items):
            pass

    first_case_specialist = Individual(1, 0.0, False, behavior=(0b01, 0))
    second_case_specialist = Individual(2, 100.0, False, behavior=(0b10, 0))

    first, second = LexicaseSelection()(
        [first_case_specialist, second_case_specialist], OrderedRandom(1)
    )

    assert first is first_case_specialist
    assert second is first_case_specialist


def test_lexicase_treats_uncovered_negative_examples_as_success():
    safe = Individual(1, 0.0, False, behavior=(0, 0))
    unsafe = Individual(2, 100.0, False, behavior=(0, 0b1))

    parents = LexicaseSelection()([unsafe, safe], random.Random(1))

    assert parents == (safe, safe)


def test_lexicase_factory_creates_strategy():
    assert isinstance(create_selection({"name": "lexicase"}), LexicaseSelection)


def test_lexicase_is_default_selection():
    assert Arguments().selection["name"] == "lexicase"


@pytest.mark.parametrize("percentage", [0.0, -0.1, 1.1])
def test_tournament_percentage_rejects_out_of_range_values(percentage):
    with pytest.raises(ValueError, match="tournament_percentage"):
        TournamentSelection(percentage, 1.0)


def test_hypothesis_generator_creates_only_closed_programs():
    rules = (
        "heads(V0):- coin(V0),not tails(V0).",
        "tails(V0):- coin(V0),not heads(V0).",
    )
    program = inductive_task(["coin(c1)."], [], [], [], [])
    space = make_clause_space(list(rules))
    generator = HypothesisGenerator(program, space, 2)

    assert [generator.render(genome) for genome in _population(generator, 1)] == [
        tuple(sorted(rules))
    ]


def test_hypothesis_generator_builds_invented_definition_module():
    consumer = "target(V0,V2) :- helper(V0,V1),helper(V1,V2)."
    mother = "helper(V0,V1) :- mother(V0,V1)."
    father = "helper(V0,V1) :- father(V0,V1)."
    recursive = "helper(V1,V0) :- helper(V0,V1)."
    constraint = ":- helper(V0,V1),bad(V0)."
    program = inductive_task(
        ["mother(a,b).", "father(b,c).", "bad(d)."],
        [example(("target(a,c)", ""), True)],
        [],
        [],
        [],
        invented_predicates=(("helper", 2),),
    )
    space = make_clause_space([consumer, mother, father, recursive, constraint])
    generator = HypothesisGenerator(program, space, 3)
    rng = random.Random(1)
    rng.randint = lambda _start, end: end

    [generated] = _population(generator, 1, rng)

    assert generated is not None
    rendered = generator.render(generated)
    assert generated.bit_count() == 3
    assert consumer in rendered
    assert mother in rendered or father in rendered


def test_population_accepts_closure_larger_than_sampled_size(monkeypatch):
    consumer = "target(V0) :- helper(V0)."
    provider = "helper(V0) :- base(V0)."
    program = inductive_task(
        ["base(a)."],
        [example(("target(a)", ""), True)],
        [],
        [],
        [],
        invented_predicates=(("helper", 1),),
    )
    generator = HypothesisGenerator(
        program,
        make_clause_space([consumer, provider]),
        2,
    )
    rng = random.Random(1)
    monkeypatch.setattr(rng, "randint", lambda _start, _end: 1)

    [generated] = _population(generator, 1, rng)

    assert generator.render(generated) == tuple(sorted((consumer, provider)))


def test_hypothesis_generator_applies_mutation_atomically():
    seed = "seed(V0) :- coin(V0)."
    consumer = "heads(V0) :- coin(V0),not tails(V0)."
    provider = "tails(V0) :- coin(V0)."
    alternative = "tails(V0) :- marked(V0)."
    program = inductive_task(["coin(c1).", "marked(c1)."], [], [], [], [])
    generator = HypothesisGenerator(
        program,
        make_clause_space([seed, consumer, provider, alternative]),
        3,
    )

    context = EvolutionContext(generator, random.Random(1))
    result = create_mutation({"name": "random_group", "probability": 1.0})(
        generator.encode((seed, consumer, provider)), context
    )

    rendered = generator.render(result.genome)
    assert rendered != tuple(sorted((seed, consumer, provider)))
    assert consumer not in rendered or provider in rendered or alternative in rendered


def test_generator_prunes_uncloseable_rules():
    program = inductive_task(["base."], [], [], [], [])
    space = make_clause_space(["base.", "target :- missing."])
    generator = HypothesisGenerator(program, space, 2)

    assert generator.space.clauses == ("base.",)
    assert [generator.render(genome) for genome in _population(generator, 2)] == [
        ("base.",)
    ]


def test_hypothesis_generator_creates_requested_population_size():
    program = inductive_task([], [], [], [], [])
    space = make_clause_space(["a.", "b.", "c."])
    generator = HypothesisGenerator(program, space, 3)

    assert len(_population(generator, 3)) == 3


def test_hypothesis_generator_uses_canonical_bitset_genomes():
    generator = HypothesisGenerator(
        inductive_task([], [], [], [], []),
        make_clause_space(["a.", "b.", "c.", "d."]),
        3,
    )

    genome = generator.encode(("c.", "a.", "c."))
    available = list(generator._random_available(genome, random.Random(1)))

    assert isinstance(genome, int)
    assert genome.bit_count() == 2
    assert generator.render(genome) == ("a.", "c.")
    assert sorted(available) == [generator.clause_ids["b."], generator.clause_ids["d."]]


def test_hypothesis_generator_does_not_cache_bounded_search_failures(monkeypatch):
    generator = HypothesisGenerator(
        inductive_task([], [], [], [], []),
        make_clause_space(["a."]),
        1,
    )
    proposal = generator.encode(("a.",))
    calls = 0

    def fail(_proposal, _forbidden, _rng):
        nonlocal calls
        calls += 1
        return None

    monkeypatch.setattr(generator, "_complete", fail)

    rng = random.Random(1)
    assert generator._build(proposal, 0, rng) is None
    assert generator._build(proposal, 0, rng) is None
    assert calls == 2


def test_hypothesis_generator_records_closure_for_each_public_transition(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "gentians.hypotheses.generator.add",
        lambda name, seconds: calls.append((name, seconds)),
    )
    generator = HypothesisGenerator(
        inductive_task([], [], [], [], []),
        make_clause_space(["a.", "b.", "c."]),
        2,
    )

    rng = random.Random(1)
    created = generator.create(rng)
    assert created is not None
    generator.append(generator.encode(("a.",)), rng)
    generator.mix(
        generator.encode(("a.",)),
        generator.encode(("b.",)),
        (0.7, 0.3),
        rng,
    )

    assert len(calls) == 3
    assert all(name.endswith(".closure") for name, _seconds in calls)


def test_evolution_strategies_choose_operations_and_delegate_validity():
    class GeneratorSpy:
        def __init__(self):
            self.calls = []

        def create(self, _rng):
            candidate = len([call for call in self.calls if call[0] == "create"]) + 1
            self.calls.append(("create", candidate))
            return candidate

        def operations(self, program):
            self.calls.append(("operations", program))
            return ["append"]

        def append(self, program, _rng):
            self.calls.append(("append", program))
            return program | 4

        def mix(self, first, second, probabilities, _rng):
            self.calls.append(("crossover", first, second, probabilities))
            return None

    generator = GeneratorSpy()
    context = EvolutionContext(generator, random.Random(1))
    genome = 1

    create_population({"name": "random", "size": 3})(context)
    create_mutation({"name": "random_group", "probability": 1.0})(genome, context)
    create_crossover({"name": "set_mix", "probability": 1.0})(genome, 2, context)

    assert [call[0] for call in generator.calls] == [
        "create",
        "create",
        "create",
        "operations",
        "append",
        "crossover",
    ]


def test_single_engine_accepts_supplied_clause_generation(monkeypatch):
    generations = []
    args = Arguments(
        random_seed=3,
        iterations_genetic=0,
        population={"name": "random", "size": 2},
    )
    monkeypatch.setattr(
        search,
        "create_population",
        lambda config: (
            lambda context: [
                context.hypotheses.encode(("good.",)),
                context.hypotheses.encode(("higher_score.",)),
            ]
        ),
    )
    monkeypatch.setattr(
        "gentians.algorithms.steady_state_genetic.create_evaluator",
        lambda program, config: (
            lambda candidate: EvaluationResult(
                1.0 if tuple(map(str, candidate)) == ("good.",) else 2.0,
                tuple(map(str, candidate)) == ("good.",),
                (1, 0) if tuple(map(str, candidate)) == ("good.",) else (0, 0),
                tuple(map(str, candidate)) == ("good.",),
                True,
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
    result = steady_state_genetic_search(
        args,
        inductive_task([], [], [], [], [], max_program_clauses=1),
        make_clause_space(["good.", "higher_score."]),
    )
    assert result.hypothesis == ("good.",)
    assert result.score == 1.0
    assert result.is_solution is True
    assert generations == [(0, 2.0, [2.0, 1.0])]


def test_search_assigns_reproducible_logical_birth_order(monkeypatch):
    orders = []
    monkeypatch.setattr(
        search,
        "create_population",
        lambda config: (
            lambda context: [
                context.hypotheses.encode(("first.",)),
                context.hypotheses.encode(("second.",)),
            ]
        ),
    )
    monkeypatch.setattr(
        search,
        "create_evaluator",
        lambda task, config: (
            lambda candidate: EvaluationResult(
                1.0,
                tuple(map(str, candidate)) == ("first.",),
                (1, 0),
                True,
                True,
            )
        ),
    )
    monkeypatch.setattr(
        search,
        "record_ga_generation",
        lambda generation, best, population, **kwargs: orders.append(
            [individual.birth_order for individual in population]
        ),
    )
    args = Arguments(random_seed=7, population={"name": "random", "size": 2})
    task = inductive_task([], [], [], [], [], max_program_clauses=1)
    space = make_clause_space(["first.", "second."])

    steady_state_genetic_search(args, task, space)
    steady_state_genetic_search(args, task, space)

    assert orders == [[1, 2], [1, 2]]


def test_default_unlimited_generations_run_until_winner(monkeypatch):
    generations = []
    args = Arguments(
        random_seed=3,
        population={"name": "random", "size": 1},
        crossover={"name": "set_mix", "probability": 1.0},
        mutation={"name": "random_group", "probability": 0.0},
    )
    monkeypatch.setattr(
        search,
        "create_population",
        lambda config: lambda context: [context.hypotheses.encode(("start.",))],
    )
    monkeypatch.setattr(
        search,
        "create_crossover",
        lambda config: (
            lambda first, second, context: context.hypotheses.encode(("win.",))
        ),
    )
    monkeypatch.setattr(
        search,
        "create_evaluator",
        lambda program, config: (
            lambda candidate: EvaluationResult(
                1.0 if tuple(map(str, candidate)) == ("win.",) else 0.0,
                tuple(map(str, candidate)) == ("win.",),
                (1, 0) if tuple(map(str, candidate)) == ("win.",) else (0, 0),
                tuple(map(str, candidate)) == ("win.",),
                True,
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

    result = steady_state_genetic_search(
        args,
        inductive_task([], [], [], [], [], max_program_clauses=1),
        make_clause_space(["start.", "win."]),
    )

    assert result.hypothesis == ("win.",)
    assert result.score == 1.0
    assert result.is_solution is True
    assert generations == [(0, 0.0, [0.0]), (1, 1.0, [1.0])]


def test_skipped_crossover_does_not_mutate_parents(monkeypatch):
    mutation_calls = []
    generations = []
    args = Arguments(
        random_seed=3,
        iterations_genetic=1,
        population={"name": "random", "size": 1},
        crossover={"name": "set_mix", "probability": 0.0},
        mutation={"name": "random_group", "probability": 1.0},
    )
    monkeypatch.setattr(
        search,
        "create_population",
        lambda config: lambda context: [context.hypotheses.encode(("start.",))],
    )
    monkeypatch.setattr(
        search,
        "create_mutation",
        lambda config: (
            lambda genome, context: (
                mutation_calls.append(genome) or MutationProposal(genome)
            )
        ),
    )
    monkeypatch.setattr(
        search,
        "create_evaluator",
        lambda program, config: lambda candidate: EvaluationResult(
            0.0, False, (0, 0), False, False
        ),
    )
    monkeypatch.setattr(
        search,
        "record_ga_generation",
        lambda generation, *_args, **_kwargs: generations.append(generation),
    )

    steady_state_genetic_search(
        args,
        inductive_task([], [], [], [], [], max_program_clauses=1),
        make_clause_space(["start."]),
    )

    assert mutation_calls == []
    assert generations == [0, 1]


def test_crossover_child_is_mutated_before_single_evaluation(monkeypatch):
    mutation_calls = []
    evaluated_programs = []
    generations = []
    args = Arguments(
        random_seed=3,
        iterations_genetic=1,
        population={"name": "random", "size": 2},
    )
    monkeypatch.setattr(
        search,
        "create_population",
        lambda config: (
            lambda context: [
                context.hypotheses.encode(("start.",)),
                context.hypotheses.encode(("loss.",)),
            ]
        ),
    )
    monkeypatch.setattr(
        search,
        "create_crossover",
        lambda config: (
            lambda first, second, context: context.hypotheses.encode(("win.",))
        ),
    )

    def destructive_mutation(genome, context):
        mutation_calls.append(genome)
        return MutationProposal(context.hypotheses.encode(("mutated.",)))

    monkeypatch.setattr(
        search,
        "create_mutation",
        lambda config: destructive_mutation,
    )
    monkeypatch.setattr(
        search,
        "create_evaluator",
        lambda program, config: (
            lambda candidate: (
                evaluated_programs.append(tuple(map(str, candidate)))
                or EvaluationResult(
                    1.0 if tuple(map(str, candidate)) == ("mutated.",) else 0.0,
                    tuple(map(str, candidate)) == ("win.",),
                    (0, 0),
                    False,
                    True,
                )
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
    result = steady_state_genetic_search(
        args,
        inductive_task([], [], [], [], []),
        make_clause_space(["start.", "win.", "loss.", "mutated."]),
    )

    assert result.hypothesis == ("mutated.",)
    assert result.score == 1.0
    assert result.is_solution is False
    assert mutation_calls
    assert ("win.",) not in evaluated_programs
    assert evaluated_programs == [("start.",), ("loss.",), ("mutated.",)]
    assert generations == [(0, 0.0, [0.0, 0.0]), (1, 1.0, [1.0, 0.0])]


def test_duplicate_crossover_base_can_produce_new_mutation(monkeypatch):
    rows = []
    evaluated_programs = []
    monkeypatch.setenv("GENTIANS_OPERATOR_METRICS_PATH", "metrics.jsonl")
    args = Arguments(
        random_seed=3,
        iterations_genetic=1,
        population={"name": "random", "size": 2},
    )
    monkeypatch.setattr(
        search,
        "create_population",
        lambda config: lambda context: [context.hypotheses.encode(("start.",))],
    )
    monkeypatch.setattr(
        search,
        "create_crossover",
        lambda config: (
            lambda first, second, context: context.hypotheses.encode(("start.",))
        ),
    )
    monkeypatch.setattr(
        search,
        "create_mutation",
        lambda config: (
            lambda genome, context: MutationProposal(
                context.hypotheses.encode(("mutated.",))
            )
        ),
    )
    monkeypatch.setattr(
        search,
        "create_evaluator",
        lambda program, config: (
            lambda candidate: (
                evaluated_programs.append(tuple(map(str, candidate)))
                or EvaluationResult(
                    1.0 if tuple(map(str, candidate)) == ("mutated.",) else 0.0,
                    False,
                    (0, 0),
                    False,
                    True,
                )
            )
        ),
    )
    monkeypatch.setattr(
        evolution_metrics, "record_metric", lambda _kind, row: rows.append(row)
    )

    steady_state_genetic_search(
        args,
        inductive_task([], [], [], [], [], max_program_clauses=1),
        make_clause_space(["start.", "mutated."]),
    )

    [crossover] = [row for row in rows if row["operator"] == "crossover"]
    [mutation] = [row for row in rows if row["operator"] == "mutation"]
    assert crossover["duplicate"] is True
    assert mutation["valid_new"] is True
    assert "new_score" not in crossover
    assert "new_score" not in mutation
    assert evaluated_programs == [("start.",), ("mutated.",)]


@pytest.mark.parametrize("mutation_name", ["random_group", "structural_neighbor"])
def test_probability_skipped_mutation_is_not_recorded_as_duplicate(
    monkeypatch, mutation_name
):
    rows = []
    monkeypatch.setenv("GENTIANS_OPERATOR_METRICS_PATH", "metrics.jsonl")
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
        lambda config: lambda context: [context.hypotheses.encode(("start.",))],
    )
    monkeypatch.setattr(
        search,
        "create_evaluator",
        lambda program, config: lambda candidate: EvaluationResult(
            1.0, False, (0, 0), False, False
        ),
    )
    monkeypatch.setattr(
        search,
        "create_crossover",
        lambda config: (
            lambda first, second, context: context.hypotheses.encode(("cross.",))
        ),
    )
    monkeypatch.setattr(
        evolution_metrics, "record_metric", lambda _kind, row: rows.append(row)
    )

    steady_state_genetic_search(
        args,
        inductive_task([], [], [], [], [], max_program_clauses=1),
        make_clause_space(["start.", "other.", "cross."]),
    )

    mutation_rows = [row for row in rows if row["operator"] == "mutation"]
    assert mutation_rows
    assert all(row["skipped"] is True for row in mutation_rows)
    assert all(row["duplicate"] is False for row in mutation_rows)


def test_equal_novel_candidate_replaces_an_existing_individual():
    population = [
        Individual(1, 0.0, False, birth_order=1),
        Individual(2, 0.0, False, birth_order=2),
    ]
    candidate = Individual(4, 0.0, False, birth_order=3)

    result = OldestOrWorstReplacement(0.0)(population, candidate, random.Random(1))

    assert candidate in result
    assert len(result) == len(population)
