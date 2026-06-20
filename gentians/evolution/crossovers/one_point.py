import random

from ..individual import Individual
from ..types import FitnessFn


def one_point_crossover(
    best_a: Individual,
    best_b: Individual,
    evaluate_score: FitnessFn,
) -> "tuple[Individual,Individual]":
    """
    Crossover: pick a random index and generate a element
    """
    crossover_position = random.randint(0, len(best_a.program) - 1)
    # print(f"Crossover: {crossover_position}")
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

    return i0, i1
