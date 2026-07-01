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
from ...rule_generation.rule_space import RuleSpace
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
) -> tuple[list[str], float, bool]:
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
    population_signatures = {individual.signature for individual in population}

    # step 1: sort in terms of decreasing fitness
    with phase("genetic.bookkeeping"):
        population.sort(key=lambda x: x.score, reverse=True)
    best = _best_individual(population)
    if best is not None:
        return _return_best(best, evaluate_score)

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
            known_signatures = set(population_signatures)
        new_program_1, new_program_2 = crossover(
            best_a,
            best_b,
            evaluate_score,
            known_signatures,
            args.max_program_clauses,
        )
        for child in (new_program_1, new_program_2):
            if child.is_best:
                return _return_best(child, evaluate_score)
            known_signatures.add(child.signature)

        # 2.3: mutation
        # https://arxiv.org/pdf/2305.01582.pdf
        new_mutated_1 = mutation(
            new_program_1,
            rule_space,
            args.max_program_clauses,
            evaluate_score,
            known_signatures,
        )
        if new_mutated_1.is_best:
            return _return_best(new_mutated_1, evaluate_score)
        known_signatures.add(new_mutated_1.signature)

        new_mutated_2 = mutation(
            new_program_2,
            rule_space,
            args.max_program_clauses,
            evaluate_score,
            known_signatures,
        )
        if new_mutated_2.is_best:
            return _return_best(new_mutated_2, evaluate_score)
        known_signatures.add(new_mutated_2.signature)

        l_mutated = [new_mutated_1, new_mutated_2]

        # 3: replace elements in the population
        for el in l_mutated:
            population = replacement(population, el, population_signatures)
        with phase("genetic.bookkeeping"):
            population.sort(key=lambda x: x.score, reverse=True)

    with phase("fitness.final"):
        res = evaluate_score(population[0].program)
    final_program = [population[0].program[i] for i in res[2]]
    final_score = res[0]
    final_best = res[1]
    if final_best:
        final_program, final_score = _minimize_best_program(
            final_program, evaluate_score
        )

    return final_program, final_score, final_best


def _best_individual(population: list[Individual]) -> Individual | None:
    return next((individual for individual in population if individual.is_best), None)


def _return_best(
    individual: Individual,
    evaluate_score: FitnessFn,
) -> tuple[list[str], float, bool]:
    indexes = individual.l_best_indexes or list(range(len(individual.program)))
    program = [individual.program[i] for i in indexes]
    program, score = _minimize_best_program(program, evaluate_score)
    return program, score, True


def _minimize_best_program(
    program: list[str],
    evaluate_score: FitnessFn,
) -> tuple[list[str], float]:
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
