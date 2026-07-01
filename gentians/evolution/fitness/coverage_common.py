from dataclasses import dataclass
from collections.abc import Callable

from ...asp.coverage import Coverage
from ...rule_generation.program import Program
from ...timing import current_phase, record_metric

FitnessResult = tuple[float, bool, list[int]]
CachedFitnessResult = tuple[float, bool, tuple[str, ...]]
FitnessCompute = Callable[[list[str]], FitnessResult]


@dataclass(frozen=True)
class CoverageRates:
    covered_positive: int
    covered_negative: int
    positive_rate: float
    negative_rate: float


def coverage_rates(program: Program, coverage: Coverage) -> CoverageRates:
    covered_positive = coverage.pos_mask.bit_count()
    covered_negative = coverage.neg_mask.bit_count()
    positive_rate = (
        covered_positive / len(program.positive_examples)
        if program.positive_examples
        else 0
    )
    negative_rate = (
        covered_negative / len(program.negative_examples)
        if program.negative_examples
        else 0
    )
    return CoverageRates(
        covered_positive,
        covered_negative,
        positive_rate,
        negative_rate,
    )


def cached_fitness(
    cache: dict[tuple[str, ...], CachedFitnessResult],
    candidate_program: list[str],
    compute: FitnessCompute,
) -> FitnessResult:
    canonical_program = sorted(candidate_program)
    key = tuple(canonical_program)
    if key not in cache:
        score, best_found, indexes = compute(canonical_program)
        cache[key] = (
            score,
            best_found,
            tuple(canonical_program[index] for index in indexes),
        )
    score, best_found, selected_rules = cache[key]
    positions_by_rule: dict[str, list[int]] = {}
    for index, rule in enumerate(candidate_program):
        positions_by_rule.setdefault(rule, []).append(index)
    indexes = []
    for rule in selected_rules:
        positions = positions_by_rule.get(rule)
        if positions:
            indexes.append(positions.pop(0))
    return score, best_found, indexes


def record_fitness_metric(
    fitness_operator: str,
    program: Program,
    candidate_program: list[str],
    coverage: Coverage,
    score: float,
    best_found: bool,
    l_index: list[int],
    rates: CoverageRates,
) -> None:
    record_metric(
        "quality",
        {
            "metric": "evaluate_score",
            "phase_context": current_phase(),
            "program_size": len(candidate_program),
            "coverage_models_positive_mask": coverage.pos_mask,
            "coverage_models_negative_mask": coverage.neg_mask,
            "score": score,
            "fitness_operator": fitness_operator,
            "best_found": best_found,
            "selected_rules": len(l_index),
            "covered_positive": rates.covered_positive,
            "covered_negative": rates.covered_negative,
            "total_positive": len(program.positive_examples),
            "total_negative": len(program.negative_examples),
        },
    )
