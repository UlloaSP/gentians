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
    rule_space: list[str],
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
    best_found = False

    population, best_found = population_initializer(
        args.max_program_clauses,
        rule_space,
        evaluate_score,
    )

    if best_found:
        record_ga_generation(0, [population[0].score], population[0].score)
        return population[0].program, population[0].score, True

    # step 1: sort in terms of decreasing fitness
    with phase("genetic.bookkeeping"):
        population.sort(key=lambda x: x.score, reverse=True)

    # step 2: iterate trough programs
    best_score_so_far = population[0].score
    for it in range(args.iterations_genetic + 1):
        with phase("genetic.bookkeeping"):
            best_score_so_far = max(best_score_so_far, population[0].score)
            record_ga_generation(it, [el.score for el in population], best_score_so_far)
        # 2.1: selection of the two fittest elements
        best_a, best_b = selection(population)

        # either do crossover or mutation seems to be not effective

        # 2.2: crossover
        with phase("genetic.bookkeeping"):
            known_signatures = {element.signature for element in population}
        new_program_1, new_program_2 = crossover(
            best_a,
            best_b,
            evaluate_score,
            known_signatures,
            args.max_program_clauses,
        )
        # If the best found, stop the iteration
        # _, is_best, l_best_indexes = evaluate_score([], [], new_program_1.program)
        for prg in [new_program_1, new_program_2]:
            if prg.is_best:
                return (
                    [prg.program[i] for i in prg.l_best_indexes],
                    prg.score,
                    True,
                )

        # 2.3: mutation
        # https://arxiv.org/pdf/2305.01582.pdf
        new_mutated_1 = mutation(
            new_program_1,
            rule_space,
            args.max_program_clauses,
            evaluate_score,
            known_signatures,
        )
        new_mutated_2 = mutation(
            new_program_2,
            rule_space,
            args.max_program_clauses,
            evaluate_score,
            known_signatures,
        )

        l_mutated = [new_mutated_1, new_mutated_2]

        # 3: replace elements in the population
        for el in l_mutated:
            # if best, return
            if el.is_best:
                return (
                    [el.program[i] for i in el.l_best_indexes],
                    el.score,
                    True,
                )

            population = replacement(population, el)
        with phase("genetic.bookkeeping"):
            population.sort(key=lambda x: x.score, reverse=True)

    with phase("fitness.final"):
        res = evaluate_score(population[0].program)

    return (
        [population[0].program[i] for i in res[2]],
        res[0],
        False,
    )
