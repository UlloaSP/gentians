import math

from ..language.ir.inductive_task import InductiveTask
from .coverage import Coverage


def coverage_score(
    task: InductiveTask, coverage: Coverage, *,
    positive_weight: float = 1.0, negative_weight: float = 1.0,
) -> float:
    positive_total = len(task.positive_examples)
    negative_total = len(task.negative_examples)
    covered_positive = coverage.pos_mask.bit_count()
    covered_negative = coverage.neg_mask.bit_count()
    if positive_total and negative_total:
        if positive_weight == negative_weight:
            numerator = covered_positive * negative_total - covered_negative * positive_total
            rate_difference = numerator / (positive_total * negative_total)
        else:
            # Weighted balanced accuracy, centered before exponentiation.
            # Counting errors keeps the perfect score exactly exp(10).
            errors = (positive_weight * (positive_total - covered_positive) * negative_total
                      + negative_weight * covered_negative * positive_total)
            rate_difference = 1 - 2 * errors / (
                (positive_weight + negative_weight) * positive_total * negative_total
            )
    elif positive_total:
        rate_difference = covered_positive / positive_total
    elif negative_total:
        rate_difference = -covered_negative / negative_total
    else:
        rate_difference = 0.0
    return math.exp(rate_difference * 10)
