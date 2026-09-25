"""Steady-state genetic search over the complete clause space."""

import random
from itertools import count

from ..arguments import Arguments
from ..clauses import ClauseSpace, generate_clause_space
from ..clauses.metrics import record_clause_space
from ..evaluation import create_evaluator
from ..evolution.crossovers import create_crossover
from ..evolution.mutations import create_mutation
from ..evolution.populations import create_population
from ..evolution.replacements import create_replacement
from ..evolution.restarts import create_restart
from ..evolution.selections import create_selection
from ..hypotheses import HypothesisGenerator
from ..language.ir.inductive_task import InductiveTask
from ..search.candidates import Candidates
from ..search.offspring import create_offspring
from ..search.population import Population
from ..search.result import SearchResult
from ..timing import phase, profile_phase
from .metrics.generations import GenerationMetrics


@profile_phase("search")
def steady_state_genetic_search(
    args: Arguments,
    task: InductiveTask,
    supplied_space: ClauseSpace | None = None,
) -> SearchResult:
    """Replace one population member per generation until a solution or the limit."""
    rng = random.Random(args.random_seed)
    initializer = create_population(args.population)
    selection = create_selection(args.selection)
    crossover = create_crossover(args.crossover)
    replacement = create_replacement(args.replacement)
    restart = create_restart(args.restart)
    operator_names = (str(args.selection["name"]), str(args.crossover["name"]), str(args.mutation["name"]))
    generations = count() if args.iterations_genetic == 0 else range(args.iterations_genetic)

    space = supplied_space if supplied_space is not None else generate_clause_space(task, args)
    record_clause_space(task, space)
    if not space:
        raise ValueError("No clauses found")
    max_program_clauses = len(space) if task.max_program_clauses is None else task.max_program_clauses
    hypotheses = HypothesisGenerator(task, space, max_program_clauses)
    if not hypotheses.space:
        raise ValueError("No clauses satisfy the hypothesis generator")
    with phase("initialization"):
        evaluator = create_evaluator(task, args.evaluation, space=hypotheses.space)
    candidates = Candidates(hypotheses, evaluator, rng)
    population = Population(candidates, initializer, replacement, str(args.replacement["name"]), 0)
    metrics = GenerationMetrics()

    with phase("initialization"):
        mutation = create_mutation(args.mutation)
        population.seed(initializer(candidates.context))
    population.rank()
    # Restarts refill to the size that initialization reached.
    population.size = len(population.members)
    if population.winner is not None:
        return _solution(population, metrics, 0)
    metrics.record(0, population)

    for generation in generations:
        if hypotheses.all_subsets_evaluated(len(candidates.evaluated)):
            break
        survivors = restart(generation, population.members, population.best, candidates.context, True)
        if survivors is not None:
            with phase("replacement"):
                population.restart(survivors, keep_members=True)
            if population.winner is not None:
                return _solution(population, metrics, generation)

        child, _ = create_offspring(population, selection, crossover, mutation, operator_names)
        if child is not None:
            population.admit_child(child)
            if child.is_solution:
                return _solution(population, metrics, generation + 1)
        population.update_best()
        metrics.record(generation + 1, population)

    return population.result()


def _solution(population: Population, metrics: GenerationMetrics, generation: int) -> SearchResult:
    metrics.record(generation, population)
    return population.result()
