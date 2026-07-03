from ...arguments import Arguments
from ..individual import Individual
from ..types import (
    CrossoverFn,
    FitnessFn,
    MutationFn,
    PopulationInitializerFn,
    ReplacementFn,
    SelectionFn,
)
from ...timing import phase, profile_phase, record_ga_generation


@profile_phase("genetic")
def genetic_solver(
    args: Arguments,
    evaluate_score: FitnessFn,
    population_initializer: PopulationInitializerFn,
    selection: SelectionFn,
    crossover: CrossoverFn,
    mutation: MutationFn,
    replacement: ReplacementFn,
) -> tuple[list[str], float, bool]:
    """
    Genetic algorithm to find the best program
    """

    # step 0: initialize the population
    population: list[Individual] = []

    population, _ = population_initializer(
        args.max_program_clauses,
        evaluate_score,
    )
    if not population:
        raise RuntimeError("Could not initialize population")

    with phase("fitness.initialization"):
        population_signatures = {individual.signature for individual in population}

    # step 1: sort in terms of decreasing fitness
    with phase("genetic.bookkeeping"):
        population.sort(key=lambda x: x.score, reverse=True)
    best = next((individual for individual in population if individual.is_best), None)
    if best is not None:
        return best.program, best.score, best.is_best
    if len(population) == 1:
        return population[0].program, population[0].score, population[0].is_best

    # step 2: iterate trough programs
    best_score_so_far = population[0].score
    for it in range(args.iterations_genetic + 1):
        with phase("genetic.bookkeeping"):
            best_score_so_far = max(best_score_so_far, population[0].score)
            generation_signatures: set[tuple[str, ...]] = set()
            record_ga_generation(
                it,
                best_score_so_far,
                population,
            )
        # 2.1: selection of the two fittest elements
        best_a, best_b = selection(population)

        # either do crossover or mutation seems to be not effective

        # 2.2: crossover
        new_program_1, new_program_2 = crossover(
            best_a,
            best_b,
            evaluate_score,
            population_signatures,
            args.max_program_clauses,
        )
        with phase("crossover"):
            for child in (new_program_1, new_program_2):
                if child.is_best:
                    return child.program, child.score, child.is_best
                generation_signatures.add(child.signature)

        # 2.3: mutation
        # https://arxiv.org/pdf/2305.01582.pdf
        new_mutated_1 = mutation(
            new_program_1,
            args.max_program_clauses,
            evaluate_score,
            population_signatures,
            generation_signatures,
        )
        with phase("mutation"):
            if new_mutated_1.is_best:
                return new_mutated_1.program, new_mutated_1.score, new_mutated_1.is_best
            generation_signatures.add(new_mutated_1.signature)

        new_mutated_2 = mutation(
            new_program_2,
            args.max_program_clauses,
            evaluate_score,
            population_signatures,
            generation_signatures,
        )
        with phase("mutation"):
            if new_mutated_2.is_best:
                return new_mutated_2.program, new_mutated_2.score, new_mutated_2.is_best
            generation_signatures.add(new_mutated_2.signature)

        # 3: replace elements in the population
        for el in (new_mutated_1, new_mutated_2):
            population = replacement(population, el, population_signatures)

    return population[0].program, population[0].score, population[0].is_best
