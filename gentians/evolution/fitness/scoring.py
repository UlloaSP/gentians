import math

from ...asp.coverage import Coverage
from ...language.ir.inductive_task import InductiveTask


def coverage_score(task: InductiveTask, coverage: Coverage) -> float:
    positive_total = len(task.positive_examples)
    negative_total = len(task.negative_examples)
    covered_positive = coverage.pos_mask.bit_count()
    covered_negative = coverage.neg_mask.bit_count()
    if positive_total and negative_total:
        numerator = (
            covered_positive * negative_total - covered_negative * positive_total
        )
        rate_difference = numerator / (positive_total * negative_total)
    elif positive_total:
        rate_difference = covered_positive / positive_total
    elif negative_total:
        rate_difference = -covered_negative / negative_total
    else:
        rate_difference = 0.0
    return math.exp(rate_difference * 10)


def balanced_coverage_score(task: InductiveTask, coverage: Coverage) -> float:
    positive_total = len(task.positive_examples)
    negative_total = len(task.negative_examples)
    covered_positive = coverage.pos_mask.bit_count()
    covered_negative = coverage.neg_mask.bit_count()
    if positive_total and negative_total:
        numerator = (
            covered_positive * negative_total
            + (negative_total - covered_negative) * positive_total
        )
        return numerator / (2 * positive_total * negative_total)
    if positive_total:
        return covered_positive / positive_total
    if negative_total:
        return (negative_total - covered_negative) / negative_total
    return 1.0
