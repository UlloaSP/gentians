import random
import time

from ..individual import Individual
from ..types import FitnessFn
from ...rule_generation.placed_clause import PlacedClause
from ...timing import phase, profile_phase, record_metric


def _clone_individual(element: Individual) -> Individual:
    return Individual(
        list(element.program),
        list(element.stub_indexes),
        list(element.prog_indexes),
        element.score,
        element.is_best,
        list(element.l_best_indexes),
    )


@profile_phase("mutation")
def mutate_by_random_stub(
    element: Individual,
    placed_list: "list[PlacedClause]",
    probability: float,
    evaluate_score: FitnessFn,
    change_stub: bool,
    known_signatures: set[tuple[str, ...]],
):
    """
    Mutation of an element
    """
    mutated_element = element
    something_changed = False
    original_score = element.score
    changed_positions = 0

    with phase("mutation.operator"):
        for i, _ in enumerate(element.program):
            if random.random() < probability:
                if not something_changed:
                    mutated_element = _clone_individual(element)
                something_changed = True
                changed_positions += 1
                # versione 1: cambio solamente il posizionamento delle variabili
                if not change_stub:
                    possibilities = placed_list[element.stub_indexes[i]]
                    rand_el = random.randint(
                        0, len(possibilities.placed_clauses) - 1
                    )
                    mutated_element.program[i] = possibilities.placed_clauses[rand_el]
                    mutated_element.prog_indexes[i] = rand_el
                else:
                    # versione 2: cambio la regola
                    new_stub = random.randint(0, len(placed_list) - 1)
                    new_prog_pos = random.randint(
                        0, len(placed_list[new_stub].placed_clauses) - 1
                    )
                    mutated_element.program[i] = placed_list[
                        new_stub
                    ].placed_clauses[new_prog_pos]
                    mutated_element.prog_indexes[i] = new_prog_pos
                    mutated_element.stub_indexes[i] = new_stub

    # TODO: add annealing to accept or reject the mutated program?
    # compute the new score if something has changed
    if something_changed:
        mutated_element.generated_timestamp = time.time()
        mutated_element.refresh_signature()
        if mutated_element.signature in known_signatures:
            mutated_element.score = float("-inf")
            mutated_element.is_best = False
            mutated_element.l_best_indexes = []
        else:
            with phase("mutation.fitness"):
                mutated_element.score, mutated_element.is_best, mutated_element.l_best_indexes = (
                    evaluate_score(
                        mutated_element.stub_indexes,
                        mutated_element.prog_indexes,
                        mutated_element.program,
                    )
            )

    record_metric(
        "operator",
        {
            "operator": "mutation",
            "strategy": "random_stub",
            "changed": something_changed,
            "changed_positions": changed_positions,
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
