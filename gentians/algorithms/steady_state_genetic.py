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
from ..evaluation import create_evaluator
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
        evaluate_candidate = create_evaluator(task, args.evaluation)

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
        result = evaluate_candidate(hypotheses.program(candidate))
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
            with phase("mutation" if mutation_changed else "crossover"):
                child = None if duplicate else admit(final_genome)
            record_mutation(
                str(args.mutation["name"]),
                crossed,
                proposal,
                duplicate=mutation_changed and duplicate,
            )
            if child is not None:
                if child.is_solution:
                    best_overall = _better(best_overall, child)
                    return finish(child, population_with(child), generation + 1)
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
    population.sort(key=lambda item: item.score, reverse=True)
    best_overall = _better(best_overall, population[0])
    return SearchResult(
        hypotheses.render(best_overall.genome),
        best_overall.score,
        best_overall.is_solution,
    )


def _better(current: Individual | None, candidate: Individual) -> Individual:
    return candidate if current is None or candidate.score > current.score else current
