import random

from ..individual import Individual
from ..program_sampler import ProgramSampler
from ..types import FitnessFn
from ...timing import instrumentation, metric_enabled, phase, profile_phase, record_metric


def _random_rule_outside(rule_pool: list[str], current_rules: set[str]) -> str | None:
    if not rule_pool:
        return None
    for _ in range(16):
        rule = random.choice(rule_pool)
        if rule not in current_rules:
            return rule
    available_rules = [rule for rule in rule_pool if rule not in current_rules]
    return random.choice(available_rules) if available_rules else None


def _has_rule_outside(rule_pool: list[str], current_rules: set[str]) -> bool:
    return bool(rule_pool) and (
        len(current_rules) < len(rule_pool)
        or any(rule not in current_rules for rule in rule_pool)
    )


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
    original_signature = element.signature
    original_score = element.score
    changed_positions = 0
    operation = "none"
    duplicate_attempts = 0
    extra_forbidden = extra_forbidden_signatures or ()

    with phase("mutation.operator"):
        if random.random() < probability:
            current_rules = set(element.program)
            rule_pool = sampler.rule_space.clauses
            has_available_rule = _has_rule_outside(rule_pool, current_rules)
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
                        rule = _random_rule_outside(rule_pool, current_rules)
                        if rule is None:
                            continue
                        candidate_program[random.randrange(len(candidate_program))] = rule
                    elif attempted_operation == "append":
                        rule = _random_rule_outside(rule_pool, current_rules)
                        if rule is None:
                            continue
                        candidate_program.append(rule)
                    else:
                        del candidate_program[random.randrange(len(candidate_program))]

                    closed = sampler.closed_program(
                        max_program_clauses,
                        forced_rules=candidate_program,
                    )
                    if closed is None:
                        continue

                    candidate_signature = tuple(closed)
                    if candidate_signature == original_signature:
                        continue
                    if (
                        candidate_signature in known_signatures
                        or candidate_signature in extra_forbidden
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
                            mutated_element.signature in known_signatures
                            or mutated_element.signature in extra_forbidden
                        )
                    ),
                    "duplicate_attempts": duplicate_attempts,
                },
            )

    return mutated_element
