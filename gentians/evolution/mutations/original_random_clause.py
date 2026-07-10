import math
import random

from ..individual import Individual, individual_from_fitness
from ..types import FitnessFn
from ...rule_generation.rule_space import RuleSpace
from ...timing import instrumentation, metric_enabled, phase, profile_phase, record_metric


@profile_phase("mutation")
def mutate_by_original_random_clause(
    element: Individual,
    max_program_clauses: int,
    probability: float,
    evaluate_score: FitnessFn,
    known_signatures: set[tuple[str, ...]],
    rule_space: RuleSpace,
    extra_forbidden_signatures: set[tuple[str, ...]] | None = None,
) -> Individual:
    original_score = element.score
    changed_positions = 0
    duplicate_population = False
    duplicate_attempts = 0
    extra_forbidden = extra_forbidden_signatures or set()

    with phase("mutation.operator"):
        candidate = list(element.program[:max_program_clauses])
        for index in range(len(candidate)):
            if random.random() < probability:
                candidate[index] = random.choice(rule_space.clauses)
                changed_positions += 1
        program = tuple(candidate)

    if not changed_positions or program == element.program:
        mutated = element
    elif program in known_signatures or program in extra_forbidden:
        duplicate_population = True
        duplicate_attempts = 1
        mutated = Individual(program, float("-inf"), False)
    else:
        with phase("mutation.fitness"):
            mutated = individual_from_fitness(program, evaluate_score(program))

    valid_new = changed_positions > 0 and math.isfinite(mutated.score)
    invalid = changed_positions > 0 and not valid_new and not duplicate_population
    if metric_enabled("operator"):
        with instrumentation():
            record_metric(
                "operator",
                {
                    "operator": "mutation",
                    "strategy": "original_random_clause",
                    "applied": changed_positions > 0,
                    "skipped": changed_positions == 0,
                    "slots": max(len(element.program), 1),
                    "changed": changed_positions > 0 and valid_new,
                    "valid_new": valid_new,
                    "invalid": invalid,
                    "duplicate": duplicate_population,
                    "failed": False,
                    "changed_positions": changed_positions,
                    "mutation_operation": "replace",
                    "probability": probability,
                    "original_score": original_score,
                    "new_score": mutated.score,
                    "improved": valid_new and mutated.score > original_score,
                    "is_best": mutated.is_best,
                    "duplicate_population": duplicate_population,
                    "duplicate_attempts": duplicate_attempts,
                },
            )

    return mutated
