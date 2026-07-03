import random

from ..individual import Individual
from ..program_sampler import ProgramSampler
from ..types import FitnessFn
from ...timing import phase, profile_phase, record_metric


def _child_from_parent(parent: Individual, program: list[str]) -> Individual:
    return Individual(program, parent.score, parent.is_best, list(parent.l_best_indexes))


def _evaluate_child(
    parent_a: Individual,
    parent_b: Individual,
    program: list[str],
    evaluate_score: FitnessFn,
    known_signatures: set[tuple[str, ...]],
) -> Individual:
    signature = tuple(sorted(program))
    if signature == parent_a.signature:
        return _child_from_parent(parent_a, program)
    if signature == parent_b.signature:
        return _child_from_parent(parent_b, program)
    if signature in known_signatures:
        return Individual(program, float("-inf"), False, [])
    with phase("crossover.fitness"):
        current_score, is_best, l_indexes = evaluate_score(program)
    return Individual(program, current_score, is_best, l_indexes)


def _sample_child(
    parent_a: Individual,
    parent_b: Individual,
    known_signatures: set[tuple[str, ...]],
    max_program_clauses: int,
    sampler: ProgramSampler,
) -> list[str]:
    union = sorted(set(parent_a.program) | set(parent_b.program))
    if not union:
        return []

    limit = max(1, min(max_program_clauses, len(union)))
    for _ in range(8):
        selected = [rule for rule in union if random.random() < 0.5]
        if not selected:
            selected = [random.choice(union)]
        if len(selected) > limit:
            selected = sorted(random.sample(selected, limit))
        else:
            selected = sorted(selected)
        child = sampler.closed_program(
            max_program_clauses,
            forced_rules=selected,
            known_signatures=known_signatures,
        )
        if child is not None:
            return child
    sampled = sampler.closed_program(
        max_program_clauses,
        known_signatures=known_signatures,
    )
    if sampled is not None:
        return sampled
    return list(random.choice((parent_a, parent_b)).program)


@profile_phase("crossover")
def set_mix_crossover(
    best_a: Individual,
    best_b: Individual,
    evaluate_score: FitnessFn,
    probability: float,
    known_signatures: set[tuple[str, ...]],
    max_program_clauses: int,
    sampler: ProgramSampler,
) -> tuple[Individual, Individual]:
    with phase("crossover.operator"):
        program_0 = _sample_child(
            best_a,
            best_b,
            known_signatures,
            max_program_clauses,
            sampler,
        )
        local_signatures = {*known_signatures, tuple(sorted(program_0))}
        program_1 = _sample_child(
            best_a,
            best_b,
            local_signatures,
            max_program_clauses,
            sampler,
        )

    i0 = _evaluate_child(best_a, best_b, program_0, evaluate_score, known_signatures)
    i1 = _evaluate_child(best_a, best_b, program_1, evaluate_score, known_signatures)

    parent_best = max(best_a.score, best_b.score)
    parent_duplicates = (
        int(i0.signature in {best_a.signature, best_b.signature})
        + int(i1.signature in {best_a.signature, best_b.signature})
    )
    duplicate_population = int(i0.score == float("-inf")) + int(i1.score == float("-inf"))
    record_metric(
        "operator",
        {
            "operator": "crossover",
            "strategy": "set_mix",
            "applied": True,
            "not_applied": False,
            "probability": probability,
            "parent_a_score": best_a.score,
            "parent_b_score": best_b.score,
            "child_1_score": i0.score,
            "child_2_score": i1.score,
            "children": 2,
            "children_improved": int(i0.score > parent_best) + int(i1.score > parent_best),
            "children_best": int(i0.is_best) + int(i1.is_best),
            "children_same_as_parent": 0,
            "children_duplicate_parent": parent_duplicates,
            "children_duplicate_population": duplicate_population,
        },
    )

    return i0, i1
