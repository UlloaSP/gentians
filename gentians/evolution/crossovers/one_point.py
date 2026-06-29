import random

from ..individual import Individual
from ..types import FitnessFn
from ...timing import phase, profile_phase, record_metric


def _child_from_parent(
    parent: Individual,
    program: list[str],
) -> Individual:
    return Individual(
        program,
        parent.score,
        parent.is_best,
        list(parent.l_best_indexes),
    )


def _evaluate_child(
    parent_a: Individual,
    parent_b: Individual,
    program: list[str],
    evaluate_score: FitnessFn,
    known_signatures: set[tuple[str, ...]],
) -> Individual:
    if program == parent_a.program:
        return _child_from_parent(parent_a, program)
    if program == parent_b.program:
        return _child_from_parent(parent_b, program)
    signature = tuple(sorted(program))
    if signature in known_signatures:
        return Individual(program, float("-inf"), False, [])
    with phase("crossover.fitness"):
        current_score, is_best, l_indexes = evaluate_score(program)
    return Individual(program, current_score, is_best, l_indexes)


def _cap_program(
    program: list[str],
    max_program_clauses: int,
    fallback: list[str],
) -> list[str]:
    capped = list(dict.fromkeys(program))[:max(1, max_program_clauses)]
    return capped if capped else [random.choice(fallback)]


@profile_phase("crossover")
def one_point_crossover(
    best_a: Individual,
    best_b: Individual,
    evaluate_score: FitnessFn,
    probability: float,
    known_signatures: set[tuple[str, ...]],
    max_program_clauses: int,
) -> "tuple[Individual,Individual]":
    """
    Crossover: pick a random index and generate a element
    """
    with phase("crossover.operator"):
        crossover_position_a = random.randint(0, len(best_a.program))
        crossover_position_b = random.randint(0, len(best_b.program))
        fallback = best_a.program + best_b.program
        new_program = _cap_program(
            best_a.program[:crossover_position_a]
            + best_b.program[crossover_position_b:],
            max_program_clauses,
            fallback,
        )
    i0 = _evaluate_child(
        best_a,
        best_b,
        new_program,
        evaluate_score,
        known_signatures,
    )

    with phase("crossover.operator"):
        new_program = _cap_program(
            best_b.program[:crossover_position_b]
            + best_a.program[crossover_position_a:],
            max_program_clauses,
            fallback,
        )
    i1 = _evaluate_child(
        best_a,
        best_b,
        new_program,
        evaluate_score,
        known_signatures,
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
            "children_duplicate_population": int(i0.score == float("-inf"))
            + int(i1.score == float("-inf")),
        },
    )

    return i0, i1
