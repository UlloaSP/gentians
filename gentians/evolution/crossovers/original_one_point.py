import math
import random

from ..individual import Individual, individual_from_fitness
from ..types import FitnessFn
from ...timing import instrumentation, metric_enabled, phase, profile_phase, record_metric


@profile_phase("crossover")
def original_one_point_crossover(
    parent_a: Individual,
    parent_b: Individual,
    evaluate_score: FitnessFn,
    probability: float,
    known_signatures: set[tuple[str, ...]],
    max_program_clauses: int,
) -> tuple[Individual, Individual] | None:
    if random.random() >= probability:
        _record_crossover(parent_a, parent_b, None, None, probability, skipped=True)
        return None
    if not parent_a.program or not parent_b.program:
        _record_crossover(parent_a, parent_b, parent_a, parent_b, probability)
        return parent_a, parent_b

    with phase("crossover.operator"):
        limit = min(len(parent_a.program), len(parent_b.program), max_program_clauses)
        position = random.randint(0, max(limit - 1, 0))
        program_0 = tuple(
            list(parent_a.program[:position]) + list(parent_b.program[position:limit])
        )
        program_1 = tuple(
            list(parent_b.program[:position]) + list(parent_a.program[position:limit])
        )

    child_0 = _evaluate_child(parent_a, parent_b, program_0, evaluate_score, known_signatures)
    child_1 = _evaluate_child(parent_b, parent_a, program_1, evaluate_score, known_signatures)
    _record_crossover(parent_a, parent_b, child_0, child_1, probability)
    return child_0, child_1


def _evaluate_child(
    parent_a: Individual,
    parent_b: Individual,
    program: tuple[str, ...],
    evaluate_score: FitnessFn,
    known_signatures: set[tuple[str, ...]],
) -> Individual:
    if program == parent_a.program:
        return Individual(program, parent_a.score, parent_a.is_best, parent_a.best_program)
    if program == parent_b.program:
        return Individual(program, parent_b.score, parent_b.is_best, parent_b.best_program)
    if program in known_signatures:
        return Individual(program, float("-inf"), False)
    with phase("crossover.fitness"):
        return individual_from_fitness(program, evaluate_score(program))


def _record_crossover(
    parent_a: Individual,
    parent_b: Individual,
    child_0: Individual | None,
    child_1: Individual | None,
    probability: float,
    skipped: bool = False,
) -> None:
    if not metric_enabled("operator"):
        return
    with instrumentation():
        children = [child for child in (child_0, child_1) if child is not None]
        parent_best = max(parent_a.score, parent_b.score)
        parent_signatures = {parent_a.program, parent_b.program}
        duplicate_parent = sum(child.program in parent_signatures for child in children)
        duplicate_population = sum(child.score == float("-inf") for child in children)
        invalid = sum(
            not math.isfinite(child.score)
            and child.program not in parent_signatures
            and child.score != float("-inf")
            for child in children
        )
        record_metric(
            "operator",
            {
                "operator": "crossover",
                "strategy": "original_one_point",
                "applied": not skipped,
                "skipped": skipped,
                "not_applied": skipped,
                "probability": probability,
                "parent_a_score": parent_a.score,
                "parent_b_score": parent_b.score,
                "child_1_score": child_0.score if child_0 is not None else "",
                "child_2_score": child_1.score if child_1 is not None else "",
                "slots": 2,
                "children": len(children),
                "children_valid_new": len(children)
                - duplicate_parent
                - duplicate_population
                - invalid,
                "children_invalid": invalid,
                "children_improved": sum(child.score > parent_best for child in children),
                "children_best": sum(child.is_best for child in children),
                "children_same_as_parent": 0,
                "children_duplicate_parent": duplicate_parent,
                "children_duplicate_population": duplicate_population,
            },
        )
