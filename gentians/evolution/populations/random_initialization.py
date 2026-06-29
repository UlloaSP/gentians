import random

from ..individual import Individual
from ..types import FitnessFn
from ...timing import profile_phase


@profile_phase("fitness.initialization")
def initialize_population(
    max_program_clauses: int,
    rule_space: list[str],
    population_size: int,
    evaluate_score: FitnessFn,
) -> tuple[list[Individual],bool]:
    """
    Initialize the population of individuals
    """
    sampled_individuals: list[Individual] = []
    best_found = False
    seen_signatures: set[tuple[str, ...]] = set()
    attempts = 0
    max_unique_attempts = population_size * 20

    while len(sampled_individuals) < population_size:
        attempts += 1
        size_limit = max(1, min(max_program_clauses, len(rule_space)))
        program_size = random.randint(1, size_limit)
        program = sorted(
            random.sample(rule_space, program_size)
        )
        signature = tuple(program)
        if signature in seen_signatures and attempts < max_unique_attempts:
            continue
        seen_signatures.add(signature)
        current_score, best_found, l_index = evaluate_score(program)

        if best_found:
            return [
                Individual(
                    [program[i] for i in l_index],
                    current_score,
                    False,
                    [],
                )
            ], best_found

        sampled_individuals.append(
            Individual(program, current_score, False, [])
        )

    return sampled_individuals, best_found
