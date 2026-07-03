from ..individual import Individual
from ..program_sampler import ProgramSampler
from ..types import FitnessFn
from ...timing import profile_phase


@profile_phase("fitness.initialization")
def initialize_population(
    max_program_clauses: int,
    population_size: int,
    evaluate_score: FitnessFn,
    sampler: ProgramSampler,
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
        program = sampler.closed_program(
            max_program_clauses,
            known_signatures=seen_signatures,
        )
        if program is None:
            if sampled_individuals:
                break
            else:
                raise RuntimeError("Could not sample a dependency-closed program")
        signature = tuple(program)
        if signature in seen_signatures:
            if attempts < max_unique_attempts:
                continue
            break
        seen_signatures.add(signature)

        current_score, is_best = evaluate_score(program)
        best_found = is_best
        sampled_individuals.append(Individual(program, current_score, is_best))
        if best_found:
            return sampled_individuals, True

    return sampled_individuals, best_found
