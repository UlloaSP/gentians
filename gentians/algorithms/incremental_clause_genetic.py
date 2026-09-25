"""Genetic search with incremental clause enumeration and bounded clause batches."""

import random
from itertools import count

from ..arguments import Arguments
from ..clauses import ClauseSpace
from ..evaluation import create_evaluator
from ..evolution.crossovers import create_crossover
from ..evolution.mutations import create_mutation
from ..evolution.populations import create_population
from ..evolution.replacements import create_replacement
from ..evolution.restarts import create_restart
from ..evolution.selections import create_selection
from ..language.ir.inductive_task import InductiveTask
from ..search.budget import SearchBudget
from ..search.candidates import Candidates
from ..search.clause_pool import IncrementalClausePool
from ..search.offspring import create_offspring
from ..search.population import Population
from ..search.renewal import probe_constraints, renew_population
from ..search.result import SearchResult
from ..timing import phase, profile_phase
from .metrics.generations import GenerationMetrics
from .metrics.incremental_epochs import EpochMetrics


@profile_phase("search")
def incremental_clause_genetic_search(
    args: Arguments,
    task: InductiveTask,
    supplied_space: ClauseSpace | None = None,
) -> SearchResult:
    """Run initialization, epoch transitions and mating until a stopping condition."""
    budget = SearchBudget(args.incremental.get("time_limit_seconds"))
    batch_size = _positive_config(args.incremental, "batch_size")
    epoch_generations = _positive_config(args.incremental, "epoch_generations")
    elite_count = _positive_config(args.incremental, "elite_count")
    archive_size = _positive_config(
        {"archive_size": args.incremental.get("archive_size", 8192)}, "archive_size",
    )
    population_size = _positive_config(args.population, "size")
    if elite_count > population_size:
        raise ValueError("incremental.elite_count cannot exceed population.size")

    rng = random.Random(args.random_seed)
    batch_seed = None if args.random_seed is None else args.random_seed ^ 0x5EED_600D
    batch_rng = random.Random(batch_seed)
    initializer = create_population(args.population)
    selection = create_selection(args.selection)
    crossover = create_crossover(args.crossover)
    mutation = create_mutation(args.mutation)
    replacement = create_replacement(args.replacement)
    restart = create_restart(args.restart)
    operator_names = (str(args.selection["name"]), str(args.crossover["name"]), str(args.mutation["name"]))
    generations = count() if args.iterations_genetic == 0 else range(args.iterations_genetic)

    try:
        with IncrementalClausePool(
            task, args, batch_size, archive_size, batch_rng, budget, supplied_space,
        ) as pool:
            hypotheses = pool.draw()
            if hypotheses is None:
                raise ValueError("Clause enumeration exhausted without a closed hypothesis")
            metrics = GenerationMetrics()
            epochs = EpochMetrics(pool)
            candidates = Candidates(hypotheses, create_evaluator(task, args.evaluation), rng, budget)
            del hypotheses  # Candidates own the current space, including after renewal.
            population = Population(
                candidates, initializer, replacement, str(args.replacement["name"]), population_size,
            )

            with phase("initialization"):
                proposals = initializer(candidates.context)
                pool.activate(candidates.hypotheses, proposals)
                population.seed(proposals)
                population.refill()
                probe_constraints(population, candidates.hypotheses.available_clauses)
                population.rank()
            if population.winner is not None:
                return _solution(population, metrics, epochs, 0)
            metrics.record(0, population)

            for generation in generations:
                budget.check()
                if (pool.exhausted and not pool.overflow
                        and candidates.hypotheses.all_subsets_evaluated(len(candidates.evaluated))):
                    epochs.end(generation, "space_exhausted", population)
                    return population.result()

                # Batch renewal replaces restarts until the finite space is exhausted.
                survivors = restart(
                    generation, population.members, population.best, candidates.context,
                    pool.exhausted,
                )
                if survivors is not None:
                    epochs.next(generation, "stagnation", population)
                    with phase("replacement"):
                        candidates.restart(survivors)
                        population.restart(survivors)
                    metrics.mark_restart()
                    if population.winner is not None:
                        return _solution(population, metrics, epochs, generation)

                if not pool.exhausted and generation - epochs.epoch_started >= epoch_generations:
                    epochs.next(generation, "generations", population)
                    with phase("replacement"):
                        renew_population(population, pool, elite_count)
                    if population.winner is not None:
                        return _solution(population, metrics, epochs, generation)

                population.update_best()
                # A batch may expose only one hypothesis; advance to the next epoch.
                if len(population.members) >= 2:
                    child, duplicate = create_offspring(
                        population, selection, crossover, mutation, operator_names,
                    )
                    epochs.duplicates += int(duplicate)
                    if child is not None:
                        population.admit_child(child)
                        if child.is_solution:
                            return _solution(population, metrics, epochs, generation + 1)
                    population.update_best()
                metrics.record(generation + 1, population)

            epochs.end(args.iterations_genetic, "generation_limit", population)
            return population.result()
    except SearchBudget.Expired:
        return budget.result()


def _solution(
    population: Population, metrics: GenerationMetrics, epochs: EpochMetrics, generation: int,
) -> SearchResult:
    epochs.end(generation, "solution", population)
    metrics.record(generation, population)
    return population.result()


def _positive_config(config: dict[str, object], name: str) -> int:
    value = config.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"incremental.{name} must be a positive integer")
    return value
