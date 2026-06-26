from dataclasses import dataclass

from ...asp.clingo import ClingoInterface
from ...asp.coverage import Coverage
from ...rule_generation.program import Program
from ...timing import current_phase, record_metric


@dataclass(frozen=True)
class CoverageRates:
    covered_positive: int
    covered_negative: int
    positive_rate: float
    negative_rate: float


def extract_program_coverage(
    program: Program,
    candidate_program: list[str],
    max_as_to_generate_foreach_program: int,
    clingo_arguments: list[str],
) -> dict[str, Coverage]:
    asp_solver = ClingoInterface(
        program.background,
        [f"{max_as_to_generate_foreach_program}", *clingo_arguments],
    )
    return asp_solver.extract_coverage_and_set_clauses(
        candidate_program,
        program.positive_examples,
        program.negative_examples,
        False,
    )


def coverage_rates(program: Program, coverage: Coverage) -> CoverageRates:
    covered_positive = len(set(coverage.l_pos))
    covered_negative = len(set(coverage.l_neg))
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


def covers_all_positive_no_negative(program: Program, rates: CoverageRates) -> bool:
    return (
        rates.covered_positive == len(program.positive_examples)
        and rates.covered_negative == 0
    )


def shortest_subset_indexes(subset_keys: list[str]) -> list[int]:
    subset_keys.sort(key=lambda s: len(s))
    return [int(v) for v in list(subset_keys[0])] if subset_keys else []


def best_subset_by_lowest_cost(cov: dict[str, Coverage]) -> list[str]:
    current_min_el = next(iter(cov.keys()))
    for key, value in cov.items():
        current = cov[current_min_el]
        if value.get_cost() < current.get_cost() or (
            value.get_cost() == current.get_cost()
            and len(key) < len(current_min_el)
        ):
            current_min_el = key
    return [current_min_el] if current_min_el != "Undefined" else []


def record_fitness_metric(
    fitness_operator: str,
    program: Program,
    candidate_program: list[str],
    cov: dict[str, Coverage],
    scores: list[float],
    score: float,
    empty_score: float,
    best_found: bool,
    l_index: list[int],
    best_key: str,
) -> None:
    best_coverage = cov.get(best_key)
    record_metric(
        "quality",
        {
            "metric": "evaluate_score",
            "phase_context": current_phase(),
            "program_size": len(candidate_program),
            "subsets_evaluated": len(cov),
            "score": score,
            "score_mean": sum(scores) / len(scores) if scores else empty_score,
            "score_max": max(scores) if scores else empty_score,
            "fitness_operator": fitness_operator,
            "best_found": best_found,
            "best_subset_size": len(l_index),
            "covered_positive": len(set(best_coverage.l_pos))
            if best_coverage is not None
            else 0,
            "covered_negative": len(set(best_coverage.l_neg))
            if best_coverage is not None
            else 0,
            "total_positive": len(program.positive_examples),
            "total_negative": len(program.negative_examples),
        },
    )
