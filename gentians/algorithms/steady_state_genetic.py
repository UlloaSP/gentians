import random
from itertools import count

from ..arguments import Arguments
from ..clauses import (
    ClauseSpace,
    generate_clause_space,
)
from ..clauses.metrics import record_clause_space
from ..language.ir.inductive_task import InductiveTask
from ..timing import (
    net_time,
    phase,
    profile_phase,
    record_ga_generation,
)
from ..evolution.crossovers import create_crossover
from ..evolution.context import EvolutionContext
from ..evolution.individual import Individual
from ..evolution.metrics import (
    operator_metrics_enabled,
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
from ..fitness import create_fitness
from ..hypotheses import Genome, HypothesisGenerator
from .result import SearchResult


@profile_phase("search")
def steady_state_genetic_search(
    args: Arguments,
    task: InductiveTask,
    supplied_space: ClauseSpace | None = None,
) -> SearchResult:
    rng = random.Random(args.random_seed)
    population_strategy = create_population(args.population)
    selection = create_selection(args.selection)
    crossover = create_crossover(args.crossover)
    replacement = create_replacement(args.replacement)
    generations = (
        count() if args.iterations_genetic == 0 else range(args.iterations_genetic)
    )

    space = (
        supplied_space
        if supplied_space is not None
        else generate_clause_space(task, args)
    )
    record_clause_space(task, space)
    if not space:
        raise ValueError("No clauses found")
    max_program_clauses = (
        len(space) if task.max_program_clauses is None else task.max_program_clauses
    )
    hypotheses = HypothesisGenerator(
        task,
        space,
        max_program_clauses,
    )
    space = hypotheses.space
    if not space:
        raise ValueError("No clauses satisfy the hypothesis generator")
    context = EvolutionContext(hypotheses, rng)

    with phase("initialization"):
        evaluate_score = create_fitness(task, args.fitness)

    evaluated: dict[Genome, Individual] = {}
    evaluations = 0
    started = net_time()

    def finish(
        solution: Individual,
        population: list[Individual],
        generation: int,
    ) -> SearchResult:
        record_ga_generation(
            generation,
            best_overall.score,
            population,
            elapsed_seconds=net_time() - started,
            fitness_evaluations=evaluations,
        )
        return SearchResult(
            hypotheses.render(solution.genome), solution.score, is_solution=True
        )

    def population_with(solution: Individual) -> list[Individual]:
        updated = replacement(list(population), solution, rng)
        return (
            updated
            if any(item is solution for item in updated)
            else [*population[:-1], solution]
        )

    def admit(candidate: Genome):
        nonlocal evaluations
        if candidate in evaluated:
            return None
        evaluations += 1
        result = evaluate_score(hypotheses.program(candidate))
        individual = Individual(
            candidate,
            result.score,
            result.is_solution,
            result.behavior,
            evaluations,
        )
        evaluated[candidate] = individual
        return individual

    with phase("initialization"):
        mutation = create_mutation(args.mutation)
        population = [
            individual
            for proposal in population_strategy(context)
            if (individual := admit(proposal)) is not None
        ]
    if not population:
        raise RuntimeError("Could not initialize population")
    population.sort(key=lambda item: item.score, reverse=True)
    best_overall = population[0]
    winner = next((item for item in population if item.is_solution), None)
    if winner is not None:
        return finish(winner, population, 0)

    record_ga_generation(
        0,
        best_overall.score,
        population,
        elapsed_seconds=net_time() - started,
        fitness_evaluations=evaluations,
    )
    for generation in generations:
        population.sort(key=lambda item: item.score, reverse=True)
        best_overall = _better(best_overall, population[0])
        with phase("selection"):
            first, second = selection(population, rng)
            record_selection(
                str(args.selection["name"]), first, second, len(population)
            )
        with phase("crossover"):
            proposals = crossover(first.genome, second.genome, context)
            if not proposals:
                record_skipped_crossover(
                    str(args.crossover["name"]), len(population)
                )
                children = []
            else:
                children = []
                for proposal in proposals:
                    existing = evaluated.get(proposal)
                    child = existing or admit(proposal)
                    if child is not None:
                        children.append((child, existing is None, True))
        for child, base_is_new, crossed in children:
            best_parent = first if first.score >= second.score else second
            if crossed:
                record_crossover(
                    str(args.crossover["name"]),
                    best_parent,
                    child,
                    child.genome,
                    duplicate=not base_is_new,
                )
            if child.is_solution:
                best_overall = _better(best_overall, child)
                return finish(child, population_with(child), generation + 1)
            with phase("mutation"):
                proposal = mutation(child.genome, context)
                duplicate = not proposal.skipped and proposal.genome in evaluated
                unchanged = proposal.genome == child.genome
                if unchanged:
                    mutated = child
                elif duplicate:
                    mutated = None
                else:
                    mutated = admit(proposal.genome)
            if operator_metrics_enabled():
                scored_mutation = (
                    evaluated.get(proposal.genome) if mutated is None else mutated
                )
                crossover_improved = crossed and child.score > best_parent.score
                record_mutation(
                    str(args.mutation["name"]),
                    child.genome,
                    child,
                    mutated,
                    proposal,
                    duplicate=duplicate,
                    crossover_strategy=str(args.crossover["name"]),
                    crossover_improved=crossover_improved,
                    lost_crossover_gain=(
                        crossover_improved
                        and scored_mutation is not None
                        and scored_mutation.score < child.score
                        and all(item.genome != child.genome for item in population)
                    ),
                )
            if mutated is None:
                continue
            if unchanged and not base_is_new:
                continue
            if mutated.is_solution:
                best_overall = _better(best_overall, mutated)
                return finish(mutated, population_with(mutated), generation + 1)
            with phase("replacement"):
                before = population
                population = replacement(population, mutated, rng)
            record_replacement(
                str(args.replacement["name"]), before, population, mutated
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
    population.sort(key=lambda item: item.score, reverse=True)
    best_overall = _better(best_overall, population[0])
    return SearchResult(
        hypotheses.render(best_overall.genome),
        best_overall.score,
        best_overall.is_solution,
    )


def _better(current: Individual | None, candidate: Individual) -> Individual:
    return candidate if current is None or candidate.score > current.score else current
