import random
import time

from ..individual import Individual
from ..program_sampler import ProgramSampler
from ..types import FitnessFn
from ...rule_generation.rule_space import RuleSpace
from ...timing import phase, profile_phase, record_metric


def _clone_individual(element: Individual) -> Individual:
    return Individual(
        list(element.program),
        element.score,
        element.is_best,
        list(element.l_best_indexes),
    )


@profile_phase("mutation")
def mutate_by_random_group(
    element: Individual,
    rule_space: RuleSpace,
    max_program_clauses: int,
    probability: float,
    evaluate_score: FitnessFn,
    known_signatures: set[tuple[str, ...]],
    sampler: ProgramSampler | None = None,
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

    with phase("mutation.operator"):
        if random.random() < probability:
            for _ in range(8):
                current_rules = set(element.program)
                available_rules = [
                    rule for rule in rule_space.clauses if rule not in current_rules
                ]
                operations = []
                if element.program and available_rules:
                    operations.append("replace")
                if len(element.program) < max_program_clauses and available_rules:
                    operations.append("append")
                if len(element.program) > 1:
                    operations.append("delete")

                if not operations:
                    break

                candidate = _clone_individual(element)
                attempted_operation = random.choice(operations)
                if attempted_operation == "replace":
                    candidate.program[random.randrange(len(candidate.program))] = (
                        random.choice(available_rules)
                    )
                elif attempted_operation == "append":
                    candidate.program.append(random.choice(available_rules))
                else:
                    del candidate.program[random.randrange(len(candidate.program))]

                if sampler is not None:
                    repaired = sampler.repair(candidate.program, max_program_clauses)
                    if repaired is None:
                        continue
                    candidate.program = repaired

                candidate.generated_timestamp = time.time()
                candidate.refresh_signature()
                if candidate.signature == original_signature:
                    continue
                if candidate.signature in known_signatures:
                    duplicate_attempts += 1
                    continue

                mutated_element = candidate
                operation = attempted_operation
                something_changed = True
                changed_positions = 1
                break

    if something_changed:
        with phase("mutation.fitness"):
            mutated_element.score, mutated_element.is_best, mutated_element.l_best_indexes = (
                evaluate_score(mutated_element.program)
            )

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
                something_changed and mutated_element.signature in known_signatures
            ),
            "duplicate_attempts": duplicate_attempts,
        },
    )

    return mutated_element
