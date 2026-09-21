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
from ..evolution.selections import create_selection
from ..language.ir.inductive_task import InductiveTask
from ..timing import phase, profile_phase
from .incremental_candidates import IncrementalCandidates
from .incremental_clause_pool import IncrementalClausePool
from .incremental_offspring import create_offspring
from .incremental_population import IncrementalPopulation
from .incremental_progress import IncrementalProgress
from .result import SearchResult
from .search_budget import SearchBudget


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
    operator_names = (str(args.selection["name"]), str(args.crossover["name"]), str(args.mutation["name"]))
    generations = count() if args.iterations_genetic == 0 else range(args.iterations_genetic)

    try:
        with IncrementalClausePool(
            task, args, batch_size, archive_size, batch_rng, budget, supplied_space,
        ) as pool:
            hypotheses = pool.draw()
            if hypotheses is None:
                raise ValueError("Clause enumeration exhausted without a closed hypothesis")
            progress = IncrementalProgress()
            candidates = IncrementalCandidates(hypotheses, create_evaluator(task, args.evaluation), rng, budget)
            del hypotheses  # The registry owns the current space, including after renewal.
            population = IncrementalPopulation(
                candidates, initializer, replacement, population_size, str(args.replacement["name"]),
            )
            with phase("initialization"):
                population.initialize(pool)
            progress_score = population.best.score
            last_progress = 0
            if population.winner is not None:
                return _solution(population, progress, 0)
            progress.generation(0, population)

            for generation in generations:
                budget.check()
                if (pool.exhausted and not pool.overflow
                        and candidates.hypotheses.all_subsets_evaluated(len(candidates.evaluated))):
                    progress.end_epoch(generation, "space_exhausted", population)
                    return population.result()
                if population.best.score > progress_score:
                    progress_score = population.best.score
                    last_progress = generation
                # Constraint-only search retains its policy: no stagnation restart.
                if (pool.exhausted and candidates.hypotheses.clauses_by_head
                        and generation - last_progress >= 100):
                    progress.next_epoch(generation, "stagnation", population)
                    last_progress = generation
                    with phase("replacement"):
                        population.restart()
                    if population.winner is not None:
                        return _solution(population, progress, generation)
                if not pool.exhausted and generation - progress.epoch_started >= epoch_generations:
                    progress.next_epoch(generation, "generations", population)
                    with phase("replacement"):
                        population.renew(pool, elite_count)
                    if population.winner is not None:
                        return _solution(population, progress, generation)

                population.update_best()
                # A batch may expose only one hypothesis; advance to the next epoch.
                if len(population.members) >= 2:
                    child, duplicate = create_offspring(
                        population, selection, crossover, mutation, operator_names,
                    )
                    progress.duplicates += int(duplicate)
                    if child is not None:
                        population.admit_child(child)
                        if child.is_solution:
                            return _solution(population, progress, generation + 1)
                    population.update_best()
                progress.generation(generation + 1, population)

            progress.end_epoch(args.iterations_genetic, "generation_limit", population)
            return population.result()
    except SearchBudget.Expired:
        return budget.result()


def _solution(
    population: IncrementalPopulation, progress: IncrementalProgress, generation: int,
) -> SearchResult:
    progress.end_epoch(generation, "solution", population)
    progress.generation(generation, population)
    return population.result()


def _positive_config(config: dict[str, object], name: str) -> int:
    value = config.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"incremental.{name} must be a positive integer")
    return value
