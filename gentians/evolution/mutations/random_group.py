import random
import time

from ..individual import Individual
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

    with phase("mutation.operator"):
        if random.random() < probability:
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

            if operations:
                mutated_element = _clone_individual(element)
                operation = random.choice(operations)
                something_changed = True
                changed_positions = 1
                if operation == "replace":
                    mutated_element.program[random.randrange(len(mutated_element.program))] = (
                        random.choice(available_rules)
                    )
                elif operation == "append":
                    mutated_element.program.append(random.choice(available_rules))
                else:
                    del mutated_element.program[random.randrange(len(mutated_element.program))]

    # TODO: add annealing to accept or reject the mutated program?
    # compute the new score if something has changed
    if something_changed:
        mutated_element.generated_timestamp = time.time()
        mutated_element.refresh_signature()
        if mutated_element.signature == original_signature:
            mutated_element = element
            something_changed = False
        elif mutated_element.signature in known_signatures:
            mutated_element.score = float("-inf")
            mutated_element.is_best = False
            mutated_element.l_best_indexes = []
        else:
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
        },
    )

    return mutated_element
