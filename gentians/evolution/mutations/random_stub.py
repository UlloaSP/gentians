import random
import time

from ..individual import Individual
from ..types import FitnessFn
from ...rule_generation.placed_clause import PlacedClause
from ...timing import phase, profile_phase, record_metric


@profile_phase("mutation")
def mutate_by_random_stub(
    element: Individual,
    placed_list: "list[PlacedClause]",
    mutation_probability: float,
    evaluate_score: FitnessFn,
    change_stub: bool = True,
):
    """
    Mutation of an element
    """
    change_stub = True
    new_element = element
    something_changed = False
    original_score = element.score
    changed_positions = 0

    with phase("mutation.operator"):
        for i, _ in enumerate(element.program):
            if random.random() < mutation_probability:
                something_changed = True
                changed_positions += 1
                # versione 1: cambio solamente il posizionamento delle variabili
                if not change_stub:
                    possibilities = placed_list[element.stub_indexes[i]]
                    rand_el = random.randint(
                        0, len(possibilities.placed_clauses) - 1
                    )
                    new_element.program[i] = possibilities.placed_clauses[rand_el]
                    new_element.prog_indexes[i] = rand_el
                else:
                    # versione 2: cambio la regola
                    new_stub = random.randint(0, len(placed_list) - 1)
                    new_prog_pos = random.randint(
                        0, len(placed_list[new_stub].placed_clauses) - 1
                    )
                    # print(f"{new_program[i]} replaced with")
                    new_element.program[i] = placed_list[
                        new_stub
                    ].placed_clauses[new_prog_pos]
                    # print(f"This: {new_program[i]}")
                    new_element.prog_indexes[i] = new_prog_pos
                    new_element.stub_indexes[i] = new_stub

    # TODO: add annealing to accept or reject the mutated program?
    # compute the new score if something has changed
    if something_changed:
        new_element.generated_timestamp = time.time()
        with phase("mutation.fitness"):
            new_element.score, new_element.is_best, new_element.l_best_indexes = (
                evaluate_score(
                    new_element.stub_indexes,
                    new_element.prog_indexes,
                    new_element.program,
                )
            )

    record_metric(
        "operator",
        {
            "operator": "mutation",
            "strategy": "random_stub",
            "changed": something_changed,
            "changed_positions": changed_positions,
            "mutation_probability": mutation_probability,
            "original_score": original_score,
            "new_score": new_element.score,
            "improved": new_element.score > original_score,
            "is_best": new_element.is_best,
        },
    )

    return new_element
