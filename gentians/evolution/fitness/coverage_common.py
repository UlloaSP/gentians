from dataclasses import dataclass
from collections.abc import Callable

from ...asp.coverage import Coverage
from ...rule_generation.program import Program
from ...timing import current_phase, record_metric

FitnessResult = tuple[float, bool]
CachedFitnessResult = tuple[float, bool]
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
        cache[key] = compute(canonical_program)
    return cache[key]


def record_fitness_metric(
    fitness_operator: str,
    program: Program,
    candidate_program: list[str],
    coverage: Coverage,
    score: float,
    best_found: bool,
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
            "selected_rules": len(candidate_program),
            "covered_positive": rates.covered_positive,
            "covered_negative": rates.covered_negative,
            "total_positive": len(program.positive_examples),
            "total_negative": len(program.negative_examples),
        },
    )
