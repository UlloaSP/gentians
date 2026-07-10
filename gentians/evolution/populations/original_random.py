import random

from ..individual import Individual, individual_from_fitness
from ..types import FitnessFn
from ...rule_generation.rule_space import RuleSpace
from ...timing import profile_phase


@profile_phase("fitness.initialization")
def initialize_original_population(
    max_program_clauses: int,
    population_size: int,
    evaluate_score: FitnessFn,
    rule_space: RuleSpace,
) -> tuple[list[Individual], bool]:
    population: list[Individual] = []
    rule_count = len(rule_space)
    if rule_count == 0:
        raise RuntimeError("Could not sample an original random program")
    sample_size = min(max_program_clauses, rule_count)

    while len(population) < population_size:
        program = tuple(
            sorted(random.sample(rule_space.clauses, sample_size))
        )
        individual = individual_from_fitness(program, evaluate_score(program))
        population.append(individual)
        if individual.is_best:
            return population, True

    return population, False
