"""Genetic search with incremental clause enumeration and bounded clause batches."""

from __future__ import annotations

import random
import math
from dataclasses import replace
from collections.abc import Sequence
from contextlib import ExitStack
from itertools import count

from ..arguments import Arguments
from ..clauses import ClauseSpace, incremental_clause_batches
from ..clauses.metrics import record_clause_space
from ..evaluation import create_evaluator
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
from .result import SearchResult


class _SearchTimeLimit(Exception):
    """Stop at an operation boundary and return the best in-budget evaluation."""


@profile_phase("search")
def incremental_clause_genetic_search(
    args: Arguments,
    task: InductiveTask,
    supplied_space: ClauseSpace | None = None,
) -> SearchResult:
    """Renew a bounded working ClauseSpace while searching complete hypotheses."""
    started_budget = net_time()
    limit = args.incremental.get("time_limit_seconds")
    if limit is not None and (
        isinstance(limit, bool) or not isinstance(limit, (int, float))
        or not math.isfinite(limit) or limit <= 0
    ):
        raise ValueError("incremental.time_limit_seconds must be a finite positive number")
    deadline = None if limit is None else started_budget + limit
    best_in_budget: SearchResult | None = None

    def check_time() -> None:
        if deadline is not None and net_time() >= deadline:
            raise _SearchTimeLimit

    batch_size = _positive_config(args.incremental, "batch_size")
    epoch_generations = _positive_config(args.incremental, "epoch_generations")
    elite_count = _positive_config(args.incremental, "elite_count")
    archive_size = _positive_config({"archive_size": args.incremental.get("archive_size", 8192)}, "archive_size")
    population_size = _positive_config(args.population, "size")
    if elite_count > population_size:
        raise ValueError("incremental.elite_count cannot exceed population.size")

    try:
        with ExitStack() as resources:
            rng = random.Random(args.random_seed)
            batch_seed = None if args.random_seed is None else args.random_seed ^ 0x5EED_600D
            batch_rng = random.Random(batch_seed)
            population_strategy = create_population(args.population)
            selection = create_selection(args.selection)
            crossover = create_crossover(args.crossover)
            mutation = create_mutation(args.mutation)
            replacement = create_replacement(args.replacement)
            generations = (
                count() if args.iterations_genetic == 0 else range(args.iterations_genetic)
            )

            source_resources = resources.enter_context(ExitStack())
            batches = (
                iter([supplied_space]) if supplied_space is not None else
                source_resources.enter_context(incremental_clause_batches(task, args, batch_size, batch_rng))
            )

            archive = {}
            exhausted = False
            overflow = False

            def draw_hypotheses(retained_entries=()) -> HypothesisGenerator | None:
                nonlocal exhausted, overflow, batches
                # Retain raw clauses before dependency pruning: their providers may arrive later.
                while True:
                    check_time()
                    batch = next(batches, None)
                    check_time()
                    if batch is None:
                        exhausted = True
                        if not overflow or supplied_space is not None or not retained_entries:
                            return None
                        source_resources.close()
                        batches = source_resources.enter_context(
                            incremental_clause_batches(task, args, batch_size, batch_rng)
                        )
                        batch = next(batches, None)
                        check_time()
                        if batch is None:
                            return None
                        exhausted = False
                    for entry in batch.entries:
                        if entry.text not in archive:
                            if len(archive) < archive_size:
                                archive[entry.text] = entry
                            else:
                                overflow = True
                    combined = ClauseSpace([*archive.values(), *retained_entries, *batch.entries])
                    limit = task.max_program_clauses or len(combined)
                    proposed = HypothesisGenerator(task, combined, limit)
                    if proposed.space and proposed.create(batch_rng) is not None:
                        record_clause_space(task, proposed.space)
                        return proposed

            hypotheses = draw_hypotheses()
            if hypotheses is None:
                raise ValueError("Clause enumeration exhausted without a closed hypothesis")
            space = hypotheses.space
            if not space:
                raise ValueError("No clauses satisfy the hypothesis generator")
            context = EvolutionContext(hypotheses, rng)

            evaluated: dict[Genome, Individual] = {}
            results: dict[Genome, EvaluationResult] = {}
            evaluations = 0
            evaluator: CandidateEvaluator
            started = net_time()
            evaluator = create_evaluator(task, args.evaluation)
            epoch_started = 0
            epoch_evaluations = 0
            epoch_duplicates = 0
            epoch_number = 0
            build_seconds = 0.0

            def record_epoch(generation: int, reason: str) -> None:
                if metric_enabled("incremental"):
                    with instrumentation():
                        record_metric(
                            "incremental",
                            {
                                "epoch": epoch_number,
                                "reason": reason,
                                "active_clauses": active_mask.bit_count(),
                                "build_seconds": build_seconds,
                                "generations": generation - epoch_started,
                                "evaluations": evaluations - epoch_evaluations,
                                "duplicates": epoch_duplicates,
                                "best_score": best_overall.score,
                            },
                        )

            def evaluate(candidate: Genome) -> EvaluationResult:
                nonlocal evaluations, best_in_budget
                check_time()
                if candidate not in results:
                    evaluations += 1
                    results[candidate] = evaluator(hypotheses.program(candidate))
                    check_time()
                    result = results[candidate]
                    if deadline is not None and (
                        best_in_budget is None or result.score > best_in_budget.score
                    ):
                        best_in_budget = SearchResult(
                            hypotheses.render(candidate), result.score, result.is_solution
                        )
                return results[candidate]

            context = EvolutionContext(hypotheses, rng, evaluate, results)

            def admit(candidate: Genome) -> Individual | None:
                if candidate in evaluated:
                    return None
                if candidate & ~hypotheses.available_clauses:
                    raise AssertionError("candidate escaped the active clause batch")
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

            def probe_constraints(population: list[Individual], additions: Genome) -> list[Individual]:
                if hypotheses.clauses_by_head or not task.positive_examples:
                    return population
                additions &= hypotheses.available_clauses
                complete = max((item for item in population if item.is_complete),
                               key=lambda item: item.score, default=None)
                for _ in range(16):
                    if any(item.is_solution for item in population):
                        break
                    base = complete.genome if complete is not None else 0
                    candidate = (
                        hypotheses.replace(base, rng, mutable=base | additions)
                        if base.bit_count() >= hypotheses.max_clauses
                        else hypotheses.append(base, rng, mutable=additions)
                    )
                    if candidate is None:
                        break
                    child = admit(candidate)
                    if child is None:
                        continue
                    if child.is_complete and (complete is None or child.score > complete.score):
                        complete = child
                    before = population
                    population = replacement(population, child, rng)
                    record_replacement(str(args.replacement["name"]), before, population, child)
                    if child.is_solution:
                        if child not in population:
                            population[-1] = child
                        break
                return population

            with phase("initialization"):
                initial_proposals = population_strategy(context)
                before_build = net_time()
                active_mask = _activate_clauses(
                    hypotheses, initial_proposals,
                    batch_size if overflow else hypotheses.clause_count, batch_rng
                )
                build_seconds = net_time() - before_build
                population = []
                for proposal in initial_proposals:
                    individual = admit(proposal)
                    if individual is not None:
                        population.append(individual)
                        if individual.is_solution:
                            break
                population = refill(population)
                population = probe_constraints(population, hypotheses.available_clauses)
            if not population:
                raise RuntimeError("Could not initialize population")
            population.sort(key=lambda item: item.score, reverse=True)
            best_overall = population[0]
            progress_score = best_overall.score
            last_progress = 0

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
                check_time()
                if best_overall.score > progress_score:
                    progress_score = best_overall.score
                    last_progress = generation
                # Preserve the constraint-only search policy; its restarts regressed.
                if (exhausted and hypotheses.clauses_by_head
                        and generation - last_progress >= 100):
                    record_epoch(generation, "stagnation")
                    epoch_number += 1
                    epoch_started = generation
                    epoch_evaluations = evaluations
                    epoch_duplicates = 0
                    last_progress = generation
                    build_seconds = 0.0
                    with phase("replacement"):
                        evaluated = {best_overall.genome: best_overall}
                        results = {best_overall.genome: results[best_overall.genome]}
                        context = EvolutionContext(hypotheses, rng, evaluate, results)
                        population = refill([best_overall])
                    winner = next((item for item in population if item.is_solution), None)
                    if winner is not None:
                        best_overall = _better(best_overall, winner)
                        return finish(winner, generation)
                if not exhausted and generation - epoch_started >= epoch_generations:
                    record_epoch(generation, "generations")
                    epoch_number += 1
                    epoch_started = generation
                    epoch_evaluations = evaluations
                    epoch_duplicates = 0
                    with phase("replacement"):
                        retained = retain_population(
                            population,
                            best_overall,
                            min(elite_count, len(population)),
                        )
                        old_hypotheses = hypotheses
                        retained_mask = 0
                        for item in retained:
                            retained_mask |= item.genome
                        retained_entries = [
                            old_hypotheses.space.entries[index]
                            for index in old_hypotheses._ids(retained_mask)
                        ]
                        proposed = draw_hypotheses(retained_entries)
                        additions = 0
                        if proposed is not None:
                            hypotheses = proposed
                            space = hypotheses.space
                            if not hypotheses.clauses_by_head:
                                additions = sum(1 << index for index, clause in enumerate(hypotheses.clauses)
                                                if clause not in old_hypotheses.clause_ids)
                            remapped = {
                                item.genome: replace(item, genome=hypotheses.encode(
                                    old_hypotheses.render(item.genome)
                                )) for item in retained
                            }
                            best_overall = remapped[best_overall.genome]
                            retained = list(remapped.values())
                            evaluated = {item.genome: item for item in retained}
                            results = {item.genome: EvaluationResult(
                                item.score, item.is_solution, item.behavior,
                                item.is_complete, item.is_consistent,
                            ) for item in retained}
                            context = EvolutionContext(hypotheses, rng, evaluate, results)
                            del remapped
                        del old_hypotheses, retained_entries, proposed
                        before_build = net_time()
                        active_mask = _activate_clauses(
                            hypotheses,
                            [item.genome for item in retained],
                            batch_size if overflow else hypotheses.clause_count,
                            batch_rng,
                        )
                        build_seconds = net_time() - before_build
                        population = refill(retained)
                        population = probe_constraints(population, additions)
                    if not population:
                        raise RuntimeError("Could not refill population after batch renewal")
                    winner = next((item for item in population if item.is_solution), None)
                    if winner is not None:
                        best_overall = _better(best_overall, winner)
                        return finish(winner, generation)

                population.sort(key=lambda item: item.score, reverse=True)
                best_overall = _better(best_overall, population[0])
                with phase("selection"):
                    first, second = selection(population, 2, rng)
                    record_selection(
                        str(args.selection["name"]), first, second, len(population)
                    )
                with phase("crossover"):
                    crossed = crossover(first.genome, second.genome, context)
                if crossed is None:
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
                    record_mutation(
                        str(args.mutation["name"]),
                        crossed,
                        proposal,
                        duplicate=mutation_changed and duplicate,
                        before=results.get(crossed),
                        after=results.get(final_genome),
                    )
                    if child is not None:
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
    except _SearchTimeLimit:
        if best_in_budget is None:
            raise RuntimeError("Time budget expired before any candidate was evaluated") from None
        return best_in_budget



def _better(current: Individual | None, candidate: Individual) -> Individual:
    return candidate if current is None or candidate.score > current.score else current


def _positive_config(config: dict[str, object], name: str) -> int:
    value = config.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"incremental.{name} must be a positive integer")
    return value


def retain_population(
    population: list[Individual], champion: Individual, count: int,
) -> list[Individual]:
    retained = sorted(population, key=lambda item: item.score, reverse=True)[:count]
    if champion not in retained:
        retained[-1] = champion
    return retained


def _activate_clauses(
    hypotheses: HypothesisGenerator,
    seeds: Sequence[Genome],
    target: int,
    rng: random.Random,
) -> Genome:
    hypotheses.set_available_clauses(hypotheses.all_clauses)
    if target >= hypotheses.clause_count:
        return hypotheses.all_clauses
    active = 0
    for genome in seeds:
        active |= genome
    target = min(target, hypotheses.clause_count)
    failures = 0
    while active.bit_count() < target and failures < 256:
        candidate = hypotheses.create(rng)
        if candidate is None or candidate & ~active == 0:
            failures += 1
            continue
        active |= candidate
        failures = 0
    if not active:
        candidate = hypotheses.create(rng)
        if candidate is None:
            raise RuntimeError("Could not construct an active clause batch")
        active = candidate
    hypotheses.set_available_clauses(active)
    return active
