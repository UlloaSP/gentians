from collections.abc import Callable

from .coverage_common import (
    best_subset_by_lowest_cost,
    cached_fitness,
    extract_program_coverage,
    FitnessResult,
    record_fitness_metric,
    score_coverage_subsets,
    shortest_subset_indexes,
)
from ...rule_generation.program import Program


def coverage_exp_mean(
    program: Program,
    max_as_to_generate_foreach_program: int,
    clingo_arguments: list[str],
    empty_score: float,
) -> Callable[[list[int], list[int], list[str]], tuple[float, bool, list[int]]]:
    cache: dict[tuple[str, ...], FitnessResult] = {}

    def evaluate_score(
        stub_indexes: list[int], prog_indexes: list[int], candidate_program: list[str]
    ) -> tuple[float, bool, list[int]]:
        return cached_fitness(
            cache,
            candidate_program,
            lambda: _evaluate_score(
                program,
                candidate_program,
                max_as_to_generate_foreach_program,
                clingo_arguments,
                empty_score,
            ),
        )

    return evaluate_score


def _evaluate_score(
    program: Program,
    candidate_program: list[str],
    max_as_to_generate_foreach_program: int,
    clingo_arguments: list[str],
    empty_score: float,
) -> FitnessResult:
    cov = extract_program_coverage(
        program,
        candidate_program,
        max_as_to_generate_foreach_program,
        clingo_arguments,
    )

    scored = score_coverage_subsets(program, cov)
    score = sum(scored.scores) / len(scored.scores) if scored.scores else empty_score

    l_best_indexes = scored.l_best_indexes
    if not scored.best_found:
        l_best_indexes = best_subset_by_lowest_cost(scored.cov)

    l_index = shortest_subset_indexes(l_best_indexes)
    best_key = l_best_indexes[0] if l_best_indexes else None
    record_fitness_metric(
        "coverage_exp_mean",
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
