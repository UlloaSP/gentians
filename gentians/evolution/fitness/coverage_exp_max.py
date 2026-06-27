from collections.abc import Callable

from .coverage_common import (
    CachedFitnessResult,
    cached_fitness,
    CoverageOracle,
    FitnessResult,
    record_fitness_metric,
    score_coverage_subsets,
    shortest_subset_indexes,
)
from ...asp.clingo import ClingoInterface
from ...rule_generation.program import Program


def coverage_exp_max(
    program: Program,
    max_as_to_generate_foreach_program: int,
    clingo_arguments: list[str],
    empty_score: float,
) -> Callable[[list[str]], tuple[float, bool, list[int]]]:
    cache: dict[tuple[str, ...], CachedFitnessResult] = {}
    coverage = CoverageOracle(
        ClingoInterface(
            program.background,
            [f"{max_as_to_generate_foreach_program}", *clingo_arguments],
        )
    )

    def evaluate_score(
        candidate_program: list[str],
    ) -> tuple[float, bool, list[int]]:
        return cached_fitness(
            cache,
            candidate_program,
            lambda canonical_program: _evaluate_score(
                program,
                canonical_program,
                coverage,
                empty_score,
            ),
        )

    return evaluate_score


def _evaluate_score(
    program: Program,
    candidate_program: list[str],
    coverage: CoverageOracle,
    empty_score: float,
) -> FitnessResult:
    cov = coverage.extract(
        candidate_program,
        program.positive_examples,
        program.negative_examples,
        False,
    )

    scored = score_coverage_subsets(program, cov)
    score = max(scored.scores) if scored.scores else empty_score

    l_best_indexes = scored.l_best_indexes
    if not scored.best_found and scored.scored_subsets:
        l_best_indexes = [
            key for key, value in scored.scored_subsets if value == score
        ]

    l_index = shortest_subset_indexes(l_best_indexes)
    best_key = l_best_indexes[0] if l_best_indexes else None
    record_fitness_metric(
        "coverage_exp_max",
        program,
        candidate_program,
        scored.cov,
        scored.scores,
        score,
        empty_score,
        scored.best_found,
        l_index,
        best_key,
        scored.rates_by_key,
    )
    return score, scored.best_found, l_index
