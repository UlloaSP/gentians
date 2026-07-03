import random

from ..individual import Individual
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

    with phase("mutation.operator"):
        if random.random() < probability:
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

                    mutated_element = Individual(closed, element.score, element.is_best)
                    operation = attempted_operation
                    something_changed = True
                    changed_positions = 1
                    break

    if something_changed:
        with phase("mutation.fitness"):
            mutated_element.score, mutated_element.is_best = evaluate_score(
                mutated_element.program
            )

    if metric_enabled("operator"):
        with instrumentation():
            record_metric(
                "operator",
                {
                    "operator": "mutation",
                    "strategy": "random_group",
                    "changed": something_changed,
                    "changed_positions": changed_positions,
                    "mutation_operation": operation,
                    "probability": probability,
                    "original_score": original_score,
                    "new_score": mutated_element.score,
                    "improved": mutated_element.score > original_score,
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
