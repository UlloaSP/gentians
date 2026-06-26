import random

from ..individual import Individual
from ..types import FitnessFn
from ...timing import phase, profile_phase, record_metric


@profile_phase("crossover")
def one_point_crossover(
    best_a: Individual,
    best_b: Individual,
    evaluate_score: FitnessFn,
    probability: float,
) -> "tuple[Individual,Individual]":
    """
    Crossover: pick a random index and generate a element
    """
    with phase("crossover.operator"):
        crossover_position = random.randint(0, len(best_a.program) - 1)
        new_program = list(
            best_a.program[:crossover_position]
            + best_b.program[crossover_position:]
        )
        new_stub_indexes = (
            best_a.stub_indexes[:crossover_position]
            + best_b.stub_indexes[crossover_position:]
        )
        new_program_indexes = (
            best_a.prog_indexes[:crossover_position]
            + best_b.prog_indexes[crossover_position:]
        )
    with phase("crossover.fitness"):
        current_score, is_best, l_indexes = evaluate_score(
            new_stub_indexes, new_program_indexes, new_program
        )
    i0 = Individual(
        new_program,
        new_stub_indexes,
        new_program_indexes,
        current_score,
        is_best,
        l_indexes,
    )

    with phase("crossover.operator"):
        new_program = list(
            best_b.program[:crossover_position]
            + best_a.program[crossover_position:]
        )
        new_stub_indexes = (
            best_b.stub_indexes[:crossover_position]
            + best_a.stub_indexes[crossover_position:]
        )
        new_program_indexes = (
            best_b.prog_indexes[:crossover_position]
            + best_a.prog_indexes[crossover_position:]
        )
    with phase("crossover.fitness"):
        current_score, is_best, l_indexes = evaluate_score(
            new_stub_indexes, new_program_indexes, new_program
        )
    i1 = Individual(
        new_program,
        new_stub_indexes,
        new_program_indexes,
        current_score,
        is_best,
        l_indexes,
    )

    parent_best = max(best_a.score, best_b.score)
    record_metric(
        "operator",
        {
            "operator": "crossover",
            "strategy": "one_point",
            "applied": True,
            "probability": probability,
            "parent_a_score": best_a.score,
            "parent_b_score": best_b.score,
            "child_1_score": i0.score,
            "child_2_score": i1.score,
            "children": 2,
            "children_improved": int(i0.score > parent_best)
            + int(i1.score > parent_best),
            "children_best": int(i0.is_best) + int(i1.is_best),
            "children_duplicate_parent": int(sorted(i0.program) == sorted(best_a.program))
            + int(sorted(i0.program) == sorted(best_b.program))
            + int(sorted(i1.program) == sorted(best_a.program))
            + int(sorted(i1.program) == sorted(best_b.program)),
        },
    )

    return i0, i1
