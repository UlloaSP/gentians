import random
import math

from ..individual import Individual, individual_from_fitness
from ..program_sampler import ProgramSampler, _random_rule_outside
from ..types import FitnessFn
from ...timing import instrumentation, metric_enabled, phase, profile_phase, record_metric


@profile_phase("mutation")
def mutate_by_random_group(
    element: Individual,
    max_program_clauses: int,
    probability: float,
    evaluate_score: FitnessFn,
    known_signatures: set[tuple[str, ...]],
    sampler: ProgramSampler,
    extra_forbidden_signatures: set[tuple[str, ...]] | None = None,
):
    """
    Mutation of an element
    """
    mutated_element = element
    something_changed = False
    original_signature = element.program
    original_score = element.score
    changed_positions = 0
    operation = "none"
    duplicate_attempts = 0
    extra_forbidden = extra_forbidden_signatures or ()
    applied = False

    with phase("mutation.operator"):
        if random.random() < probability:
            applied = True
            current_rules = set(element.program)
            rule_pool = sampler.rule_space.clauses
            has_available_rule = len(current_rules) < len(rule_pool)
            operations = []
            if element.program and has_available_rule:
                operations.append("replace")
            if len(element.program) < max_program_clauses and has_available_rule:
                operations.append("append")
            if len(element.program) > 1:
                operations.append("delete")

            if operations:
                for _ in range(8):
                    candidate_program = list(element.program)
                    attempted_operation = random.choice(operations)
                    if attempted_operation == "replace":
                        rule = _random_rule_outside(rule_pool, set(candidate_program))
                        if rule is None:
                            continue
                        candidate_program[random.randrange(len(candidate_program))] = rule
                    elif attempted_operation == "append":
                        rule = _random_rule_outside(rule_pool, set(candidate_program))
                        if rule is None:
                            continue
                        candidate_program.append(rule)
                    else:
                        del candidate_program[random.randrange(len(candidate_program))]

                    closed = sampler.closed_program(
                        max_program_clauses,
                        forced_rules=tuple(candidate_program),
                    )
                    if closed is None:
                        continue

                    if closed == original_signature:
                        continue
                    if (
                        closed in known_signatures
                        or closed in extra_forbidden
                    ):
                        duplicate_attempts += 1
                        continue

                    mutated_element = Individual(
                        closed, element.score, element.is_best, element.best_program
                    )
                    operation = attempted_operation
                    something_changed = True
                    changed_positions = 1
                    break

    valid_new = something_changed and math.isfinite(mutated_element.score)
    invalid = something_changed and not math.isfinite(mutated_element.score)
    duplicate = applied and not something_changed and duplicate_attempts > 0
    failed = applied and not something_changed and duplicate_attempts == 0

    if something_changed:
        with phase("mutation.fitness"):
            mutated_element = individual_from_fitness(
                mutated_element.program, evaluate_score(mutated_element.program)
            )
        valid_new = math.isfinite(mutated_element.score)
        invalid = not valid_new

    if metric_enabled("operator"):
        with instrumentation():
            record_metric(
                "operator",
                {
                    "operator": "mutation",
                    "strategy": "random_group",
                    "applied": applied,
                    "skipped": not applied,
                    "slots": 1,
                    "changed": something_changed,
                    "valid_new": valid_new,
                    "invalid": invalid,
                    "duplicate": duplicate,
                    "failed": failed,
                    "changed_positions": changed_positions,
                    "mutation_operation": operation,
                    "probability": probability,
                    "original_score": original_score,
                    "new_score": mutated_element.score,
                    "improved": valid_new and mutated_element.score > original_score,
                    "is_best": mutated_element.is_best,
                    "duplicate_population": (
                        something_changed
                        and (
                            mutated_element.program in known_signatures
                            or mutated_element.program in extra_forbidden
                        )
                    ),
                    "duplicate_attempts": duplicate_attempts,
                },
            )

    return mutated_element
