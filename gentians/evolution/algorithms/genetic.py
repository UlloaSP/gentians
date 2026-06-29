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
from ...rule_generation.rule_space import RuleId, RuleSpace
from ...timing import phase, profile_phase, record_ga_generation


@profile_phase("genetic")
def genetic_solver(
    rule_space: RuleSpace,
    args: Arguments,
    evaluate_score: FitnessFn,
    population_initializer: PopulationInitializerFn,
    selection: SelectionFn,
    crossover: CrossoverFn,
    mutation: MutationFn,
    replacement: ReplacementFn,
) -> tuple[list[RuleId], float, bool]:
    """
    Genetic algorithm to find the best program
    """

    # step 0: initialize the population
    population: list[Individual] = []

    population, _ = population_initializer(
        args.max_program_clauses,
        rule_space,
        evaluate_score,
    )

    # step 1: sort in terms of decreasing fitness
    with phase("genetic.bookkeeping"):
        population.sort(key=lambda x: x.score, reverse=True)

    # step 2: iterate trough programs
    best_score_so_far = population[0].score
    for it in range(args.iterations_genetic + 1):
        with phase("genetic.bookkeeping"):
            best_score_so_far = max(best_score_so_far, population[0].score)
            record_ga_generation(
                it,
                [el.score for el in population],
                best_score_so_far,
                population,
            )
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
            population = replacement(population, el)
        with phase("genetic.bookkeeping"):
            population.sort(key=lambda x: x.score, reverse=True)

    with phase("fitness.final"):
        res = evaluate_score(population[0].program)
    final_program = [population[0].program[i] for i in res[2]]
    final_score = res[0]
    final_best = res[1]
    if final_best:
        final_program, final_score = _minimize_best_program(final_program, evaluate_score)

    return final_program, final_score, final_best


def _minimize_best_program(
    program: list[RuleId],
    evaluate_score: FitnessFn,
) -> tuple[list[RuleId], float]:
    current = list(program)
    current_score, _, _ = evaluate_score(current)
    changed = True
    while changed and len(current) > 1:
        changed = False
        for index in range(len(current)):
            candidate = current[:index] + current[index + 1 :]
            score, best_found, selected = evaluate_score(candidate)
            if best_found:
                current = [candidate[i] for i in selected]
                current_score = score
                changed = True
                break
    return current, current_score
