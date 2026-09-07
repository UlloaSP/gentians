"""Genetic search using a frozen clause pool per epoch."""

from __future__ import annotations

import random
from dataclasses import replace
from itertools import count

from ..arguments import Arguments
from ..clauses import ClauseSpace, generate_clause_space, sample_clause_space
from ..clauses.metrics import record_clause_space
from ..evaluation import create_epoch_pool_evaluator, create_evaluator
from ..evaluation.compiler import compile_coverage_program
from ..evaluation.evaluator import CandidateEvaluator
from ..evaluation.result import EvaluationResult
from ..evolution.context import EvolutionContext
from ..evolution.crossovers import create_crossover
from ..evolution.individual import Individual
from ..evolution.metrics import (
    record_crossover,
    record_mutation,
    record_replacement,
    record_selection,
    record_skipped_crossover,
)
from ..evolution.mutations import create_mutation
from ..evolution.populations import create_population
from ..evolution.replacements import create_replacement
from ..evolution.reproduction import ReproductiveHistory
from ..evolution.selections import create_selection
from ..hypotheses import Genome, HypothesisGenerator
from ..language.ir.inductive_task import InductiveTask
from ..timing import (
    instrumentation,
    metric_enabled,
    net_time,
    phase,
    profile_phase,
    record_ga_generation,
    record_metric,
)
from .pool_policy import build_clause_pool, renewal_reason, retain_population
from .result import SearchResult


@profile_phase("search")
def epoch_pool_genetic_search(
    args: Arguments,
    task: InductiveTask,
    supplied_space: ClauseSpace | None = None,
) -> SearchResult:
    """Run the GA while rebuilding one bounded, jointly grounded clause pool."""
    pool_size = _positive_config(args.clause_pool, "size")
    source = _choice_config(args.clause_pool, "source", "sampled", {"sampled", "exhaustive"})
    sampled = source == "sampled" and supplied_space is None
    epoch_generations = _positive_config(args.clause_pool, "epoch_generations")
    elite_count = _positive_config(args.clause_pool, "elite_count")
    solver_policy = _choice_config(
        args.clause_pool, "solver", "persistent", {"fresh", "persistent"}
    )
    retention = _choice_config(
        args.clause_pool,
        "retention",
        "fitness",
        {"fitness", "behavior", "reproductive"},
    )
    filling = _choice_config(
        args.clause_pool, "filling", "random", {"random", "neighbors"}
    )
    renewal = _choice_config(
        args.clause_pool, "renewal", "generations", {"generations", "adaptive"}
    )
    evaluation_budget = _positive_config(
        {"epoch_evaluations": args.clause_pool.get("epoch_evaluations", 50)},
        "epoch_evaluations",
    )
    population_size = _positive_config(args.population, "size")
    if elite_count > population_size:
        raise ValueError("clause_pool.elite_count cannot exceed population.size")

    rng = random.Random(args.random_seed)
    pool_seed = None if args.random_seed is None else args.random_seed ^ 0x5EED_600D
    pool_rng = random.Random(pool_seed)
    population_strategy = create_population(args.population)
    history = (
        ReproductiveHistory()
        if retention == "reproductive"
        or args.selection["name"] == "reproductive_lexicase"
        else None
    )
    selection = create_selection(args.selection, history=history)
    crossover = create_crossover(args.crossover)
    mutation = create_mutation(args.mutation)
    replacement = create_replacement(args.replacement)
    generations = (
        count() if args.iterations_genetic == 0 else range(args.iterations_genetic)
    )

    def draw_hypotheses(retained_entries=()) -> HypothesisGenerator:
        # A batch may lack dependency providers. Retry without accumulating history.
        for _ in range(64):
            batch = sample_clause_space(task, args, pool_size, pool_rng)
            combined = ClauseSpace([*retained_entries, *batch.entries])
            limit = task.max_program_clauses or len(combined)
            proposed = HypothesisGenerator(task, combined, limit)
            if proposed.space and proposed.create(pool_rng) is not None:
                record_clause_space(task, proposed.space)
                return proposed
        raise RuntimeError("Could not sample a clause batch with a closed hypothesis")

    space = (
        supplied_space
        if supplied_space is not None
        else ClauseSpace([]) if sampled
        else generate_clause_space(task, args)
    )
    if not sampled:
        record_clause_space(task, space)
    if not space and not sampled:
        raise ValueError("No clauses found")
    max_clauses = (
        len(space) if task.max_program_clauses is None else task.max_program_clauses
    )
    hypotheses = draw_hypotheses() if sampled else HypothesisGenerator(task, space, max_clauses)
    space = hypotheses.space
    if not space:
        raise ValueError("No clauses satisfy the hypothesis generator")
    context = EvolutionContext(hypotheses, rng)

    evaluated: dict[Genome, Individual] = {}
    results: dict[Genome, EvaluationResult] = {}
    evaluations = 0
    evaluator: CandidateEvaluator
    started = net_time()
    coverage_program = (
        compile_coverage_program(task.positive_examples, task.negative_examples)
        if solver_policy == "persistent"
        else None
    )
    fresh_evaluator = (
        create_evaluator(task, args.evaluation) if solver_policy == "fresh" else None
    )
    epoch_started = 0
    epoch_evaluations = 0
    epoch_duplicates = 0
    last_progress = 0
    epoch_number = 0
    build_seconds = 0.0
    setup_seconds = 0.0

    def record_epoch(generation: int, reason: str) -> None:
        if metric_enabled("pool"):
            with instrumentation():
                record_metric(
                    "pool",
                    {
                        "epoch": epoch_number,
                        "reason": reason,
                        "pool_size": pool_mask.bit_count(),
                        "build_seconds": build_seconds,
                        "solver_setup_seconds": setup_seconds,
                        "generations": generation - epoch_started,
                        "evaluations": evaluations - epoch_evaluations,
                        "duplicates": epoch_duplicates,
                        "best_score": best_overall.score,
                    },
                )

    def make_evaluator(pool_mask: Genome) -> CandidateEvaluator:
        if fresh_evaluator is not None:
            return fresh_evaluator
        entries = []
        remaining = pool_mask
        while remaining:
            bit = remaining & -remaining
            entries.append(space.entries[bit.bit_length() - 1])
            remaining ^= bit
        pool = ClauseSpace(entries)
        with phase("pregrounding"):
            return create_epoch_pool_evaluator(
                task, args.evaluation, pool, coverage_program=coverage_program
            )

    def evaluate(candidate: Genome) -> EvaluationResult:
        nonlocal evaluations
        if candidate not in results:
            evaluations += 1
            results[candidate] = evaluator(hypotheses.program(candidate))
        return results[candidate]

    context = EvolutionContext(hypotheses, rng, evaluate, results)

    def admit(candidate: Genome) -> Individual | None:
        if candidate in evaluated:
            return None
        if candidate & ~hypotheses.available_clauses:
            raise AssertionError("candidate escaped the frozen clause pool")
        result = evaluate(candidate)
        individual = Individual(
            genome=candidate,
            score=result.score,
            is_solution=result.is_solution,
            behavior=result.behavior,
            birth_order=evaluations,
            is_complete=result.is_complete,
            is_consistent=result.is_consistent,
        )
        evaluated[candidate] = individual
        return individual

    def refill(seed: list[Individual]) -> list[Individual]:
        target = population_size
        population = list(dict.fromkeys(seed))
        if any(item.is_solution for item in population):
            return population
        attempts = 0
        while len(population) < target and attempts < 64:
            proposals = population_strategy(context)
            added = False
            for proposal in proposals:
                individual = evaluated.get(proposal)
                if individual is None:
                    individual = admit(proposal)
                if individual is not None and individual not in population:
                    population.append(individual)
                    added = True
                    if individual.is_solution:
                        return population
                    if len(population) == target:
                        break
            attempts = 0 if added else attempts + 1
        return population

    with phase("initialization"):
        initial_proposals = population_strategy(context)
        before_build = net_time()
        pool_mask = build_clause_pool(
            hypotheses, initial_proposals, pool_size, filling, pool_rng
        )
        build_seconds = net_time() - before_build
        before_setup = net_time()
        evaluator = make_evaluator(pool_mask)
        setup_seconds = net_time() - before_setup
        population = []
        for proposal in initial_proposals:
            individual = admit(proposal)
            if individual is not None:
                population.append(individual)
                if individual.is_solution:
                    break
        population = refill(population)
    if not population:
        raise RuntimeError("Could not initialize population")
    population.sort(key=lambda item: item.score, reverse=True)
    best_overall = population[0]
    behaviors = {item.behavior for item in population}

    def finish(solution: Individual, generation: int) -> SearchResult:
        record_epoch(generation, "solution")
        record_ga_generation(
            generation,
            best_overall.score,
            population,
            elapsed_seconds=net_time() - started,
            fitness_evaluations=evaluations,
        )
        return SearchResult(hypotheses.render(solution.genome), solution.score, True)

    def population_with(solution: Individual) -> list[Individual]:
        updated = replacement(list(population), solution, rng)
        return (
            updated
            if any(item is solution for item in updated)
            else [*population[:-1], solution]
        )

    winner = next((item for item in population if item.is_solution), None)
    if winner is not None:
        return finish(winner, 0)
    record_ga_generation(
        0,
        best_overall.score,
        population,
        elapsed_seconds=net_time() - started,
        fitness_evaluations=evaluations,
    )

    for generation in generations:
        reason = renewal_reason(
            renewal,
            generation - epoch_started,
            generation - last_progress,
            evaluations - epoch_evaluations,
            epoch_duplicates,
            epoch_generations,
            evaluation_budget,
        )
        if reason is not None:
            record_epoch(generation, reason)
            epoch_number += 1
            epoch_started = last_progress = generation
            epoch_evaluations = evaluations
            epoch_duplicates = 0
            with phase("replacement"):
                retained = retain_population(
                    population,
                    best_overall,
                    min(elite_count, len(population)),
                    retention,
                    history,
                )
                if history is not None:
                    history.decay()
                del evaluator
                if sampled:
                    old_hypotheses = hypotheses
                    retained_mask = 0
                    for item in retained:
                        retained_mask |= item.genome
                    retained_entries = [
                        old_hypotheses.space.entries[index]
                        for index in old_hypotheses._ids(retained_mask)
                    ]
                    hypotheses = draw_hypotheses(retained_entries)
                    space = hypotheses.space
                    remapped = {
                        item.genome: replace(item, genome=hypotheses.encode(
                            old_hypotheses.render(item.genome)
                        )) for item in retained
                    }
                    best_overall = remapped[best_overall.genome]
                    retained = list(remapped.values())
                    if history is not None:
                        history.remap({old: item.genome for old, item in remapped.items()})
                    evaluated = {item.genome: item for item in retained}
                    results = {item.genome: EvaluationResult(
                        item.score, item.is_solution, item.behavior,
                        item.is_complete, item.is_consistent,
                    ) for item in retained}
                    context = EvolutionContext(hypotheses, rng, evaluate, results)
                    behaviors = {item.behavior for item in retained}
                    del old_hypotheses, retained_entries, remapped
                before_build = net_time()
                pool_mask = build_clause_pool(
                    hypotheses,
                    [item.genome for item in retained],
                    pool_size,
                    filling,
                    pool_rng,
                )
                build_seconds = net_time() - before_build
                before_setup = net_time()
                evaluator = make_evaluator(pool_mask)
                setup_seconds = net_time() - before_setup
                population = refill(retained)
                behaviors.update(item.behavior for item in population)
            if not population:
                raise RuntimeError("Could not refill population after pool rebuild")
            winner = next((item for item in population if item.is_solution), None)
            if winner is not None:
                best_overall = _better(best_overall, winner)
                return finish(winner, generation)

        population.sort(key=lambda item: item.score, reverse=True)
        best_overall = _better(best_overall, population[0])
        with phase("selection"):
            first, second = selection(population, rng)
            record_selection(
                str(args.selection["name"]), first, second, len(population)
            )
        with phase("crossover"):
            crossed = crossover(first.genome, second.genome, context)
        if crossed is None:
            if history is not None:
                history.observe(first, second, None)
            record_skipped_crossover(str(args.crossover["name"]), len(population))
        else:
            best_parent = first if first.score >= second.score else second
            record_crossover(
                str(args.crossover["name"]),
                best_parent.genome,
                crossed,
                duplicate=crossed in evaluated,
            )
            with phase("mutation"):
                proposal = mutation(crossed, context)
            final_genome = proposal.genome
            mutation_changed = final_genome != crossed
            duplicate = final_genome in evaluated
            epoch_duplicates += int(duplicate)
            with phase("mutation" if mutation_changed else "crossover"):
                child = None if duplicate else admit(final_genome)
            if history is not None:
                history.observe(first, second, child, duplicate)
            record_mutation(
                str(args.mutation["name"]),
                crossed,
                proposal,
                duplicate=mutation_changed and duplicate,
            )
            if child is not None:
                if child.score > best_overall.score or child.behavior not in behaviors:
                    last_progress = generation + 1
                behaviors.add(child.behavior)
                if child.is_solution:
                    best_overall = _better(best_overall, child)
                    population = population_with(child)
                    return finish(child, generation + 1)
                with phase("replacement"):
                    before = population
                    population = replacement(population, child, rng)
                record_replacement(
                    str(args.replacement["name"]), before, population, child
                )
        population.sort(key=lambda item: item.score, reverse=True)
        best_overall = _better(best_overall, population[0])
        if history is not None:
            history.retain([best_overall.genome, *(item.genome for item in population)])
        record_ga_generation(
            generation + 1,
            best_overall.score,
            population,
            elapsed_seconds=net_time() - started,
            fitness_evaluations=evaluations,
        )

    record_epoch(args.iterations_genetic, "generation_limit")
    return SearchResult(
        hypotheses.render(best_overall.genome),
        best_overall.score,
        best_overall.is_solution,
    )


def _better(current: Individual | None, candidate: Individual) -> Individual:
    return candidate if current is None or candidate.score > current.score else current


def _positive_config(config: dict[str, object], name: str) -> int:
    value = config.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"clause_pool.{name} must be a positive integer")
    return value


def _choice_config(
    config: dict[str, object], name: str, default: str, choices: set[str]
) -> str:
    value = str(config.get(name, default))
    if value not in choices:
        raise ValueError(f"clause_pool.{name} must be one of {sorted(choices)}")
    return value
