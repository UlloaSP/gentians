import random

from ..individual import Individual
from ..types import FitnessFn
from ...timing import phase, profile_phase, record_metric


def _child_from_parent(
    parent: Individual,
    program: list[str],
    stub_indexes: list[int],
    prog_indexes: list[int],
) -> Individual:
    return Individual(
        program,
        stub_indexes,
        prog_indexes,
        parent.score,
        parent.is_best,
        list(parent.l_best_indexes),
    )


def _evaluate_child(
    parent_a: Individual,
    parent_b: Individual,
    program: list[str],
    stub_indexes: list[int],
    prog_indexes: list[int],
    evaluate_score: FitnessFn,
) -> Individual:
    if program == parent_a.program:
        return _child_from_parent(parent_a, program, stub_indexes, prog_indexes)
    if program == parent_b.program:
        return _child_from_parent(parent_b, program, stub_indexes, prog_indexes)
    with phase("crossover.fitness"):
        current_score, is_best, l_indexes = evaluate_score(
            stub_indexes, prog_indexes, program
        )
    return Individual(program, stub_indexes, prog_indexes, current_score, is_best, l_indexes)


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
    i0 = _evaluate_child(
        best_a,
        best_b,
        new_program,
        new_stub_indexes,
        new_program_indexes,
        evaluate_score,
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
    i1 = _evaluate_child(
        best_a,
        best_b,
        new_program,
        new_stub_indexes,
        new_program_indexes,
        evaluate_score,
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
            "children_duplicate_parent": int(i0.signature == best_a.signature)
            + int(i0.signature == best_b.signature)
            + int(i1.signature == best_a.signature)
            + int(i1.signature == best_b.signature),
        },
    )

    return i0, i1
