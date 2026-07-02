import random

from ..individual import Individual
from ..program_sampler import ProgramSampler
from ..types import FitnessFn
from ...rule_generation.rule_space import RuleSpace
from ...timing import profile_phase


@profile_phase("fitness.initialization")
def initialize_population(
    max_program_clauses: int,
    rule_space: RuleSpace,
    population_size: int,
    evaluate_score: FitnessFn,
    sampler: ProgramSampler | None = None,
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
        if sampler is None:
            program_size = random.randint(1, size_limit)
            program = sorted(random.sample(rule_space.clauses, program_size))
        else:
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
        current_score, best_found, l_index = evaluate_score(program)

        sampled_individuals.append(Individual(program, current_score, best_found, l_index))
        if best_found:
            return sampled_individuals, True

    return sampled_individuals, best_found
