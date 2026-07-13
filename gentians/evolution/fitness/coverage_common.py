from collections.abc import Callable

from ...asp.coverage import Coverage
from ...rule_generation.program import Program
from ...timing import current_phase, instrumentation, metric_enabled, record_metric

FitnessResult = tuple[float, bool] | tuple[float, bool, tuple[str, ...] | None]
CachedFitnessResult = FitnessResult
FitnessCompute = Callable[[tuple[str, ...]], FitnessResult]


def cached_fitness(
    cache: dict[tuple[str, ...], CachedFitnessResult],
    candidate_program: tuple[str, ...],
    compute: FitnessCompute,
) -> FitnessResult:
    if candidate_program not in cache:
        cache[candidate_program] = compute(candidate_program)
    return cache[candidate_program]


def record_fitness_metric(
    fitness_operator: str,
    program: Program,
    candidate_program: tuple[str, ...],
    coverage: Coverage,
    score: float,
    best_found: bool,
    details: dict[str, object] | None = None,
) -> None:
    if not metric_enabled("quality"):
        return
    with instrumentation():
        covered_positive = coverage.pos_mask.bit_count()
        covered_negative = coverage.neg_mask.bit_count()
        payload: dict[str, object] = {
            "metric": "evaluate_score",
            "phase_context": current_phase(),
            "program_size": len(candidate_program),
            "coverage_models_positive_mask": coverage.pos_mask,
            "coverage_models_negative_mask": coverage.neg_mask,
            "score": score,
            "fitness_operator": fitness_operator,
            "best_found": best_found,
            "selected_rules": len(candidate_program),
            "covered_positive": covered_positive,
            "covered_negative": covered_negative,
            "total_positive": len(program.positive_examples),
            "total_negative": len(program.negative_examples),
        }
        if details:
            payload.update(details)
        record_metric(
            "quality",
            payload,
        )
