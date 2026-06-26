from dataclasses import dataclass
from collections.abc import Callable
import math

from ...asp.clingo import ClingoInterface
from ...asp.coverage import Coverage
from ...rule_generation.program import Program
from ...timing import current_phase, record_metric

CoverageKey = tuple[int, ...]
FitnessResult = tuple[float, bool, list[int]]


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
) -> dict[CoverageKey, Coverage]:
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


def shortest_subset_indexes(subset_keys: list[CoverageKey]) -> list[int]:
    subset_keys.sort(key=len)
    return list(subset_keys[0]) if subset_keys else []


def best_subset_by_lowest_cost(cov: dict[CoverageKey, Coverage]) -> list[CoverageKey]:
    if not cov:
        return []
    current_min_el = next(iter(cov.keys()))
    current_min_cost = cov[current_min_el].get_cost()
    for key, value in cov.items():
        value_cost = value.get_cost()
        if value_cost < current_min_cost or (
            value_cost == current_min_cost
            and len(key) < len(current_min_el)
        ):
            current_min_el = key
            current_min_cost = value_cost
    return [current_min_el]


@dataclass(frozen=True)
class ScoredCoverage:
    cov: dict[CoverageKey, Coverage]
    scored_subsets: list[tuple[CoverageKey, float]]
    scores: list[float]
    best_found: bool
    l_best_indexes: list[CoverageKey]
    rates_by_key: dict[CoverageKey, CoverageRates]


def score_coverage_subsets(program: Program, cov: dict[CoverageKey, Coverage]) -> ScoredCoverage:
    best_found = False
    l_best_indexes: list[CoverageKey] = []
    scored_subsets: list[tuple[CoverageKey, float]] = []
    rates_by_key: dict[CoverageKey, CoverageRates] = {}

    for key, element_coverage in cov.items():
        rates = coverage_rates(program, element_coverage)
        rates_by_key[key] = rates
        scored_subsets.append(
            (key, math.exp((rates.positive_rate - rates.negative_rate) * 10))
        )
        if covers_all_positive_no_negative(program, rates):
            l_best_indexes.append(key)
            best_found = True

    return ScoredCoverage(
        cov,
        scored_subsets,
        [score for _, score in scored_subsets],
        best_found,
        l_best_indexes,
        rates_by_key,
    )


def cached_fitness(
    cache: dict[tuple[str, ...], FitnessResult],
    candidate_program: list[str],
    compute: "Callable[[], FitnessResult]",
) -> FitnessResult:
    key = tuple(candidate_program)
    if key not in cache:
        cache[key] = compute()
    return cache[key]


def record_fitness_metric(
    fitness_operator: str,
    program: Program,
    candidate_program: list[str],
    cov: dict[CoverageKey, Coverage],
    scores: list[float],
    score: float,
    empty_score: float,
    best_found: bool,
    l_index: list[int],
    best_key: CoverageKey | None,
    rates_by_key: dict[CoverageKey, CoverageRates],
) -> None:
    best_rates = rates_by_key.get(best_key) if best_key is not None else None
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
            "covered_positive": best_rates.covered_positive if best_rates else 0,
            "covered_negative": best_rates.covered_negative if best_rates else 0,
            "total_positive": len(program.positive_examples),
            "total_negative": len(program.negative_examples),
        },
    )
