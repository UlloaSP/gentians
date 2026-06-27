from collections.abc import Callable

from .coverage_common import (
    CachedFitnessResult,
    best_subset_by_lowest_cost,
    cached_fitness,
    FitnessResult,
    record_fitness_metric,
    score_coverage_subsets,
    shortest_subset_indexes,
)
from ...asp.clingo import ClingoInterface
from ...rule_generation.program import Program


def coverage_exp_mean(
    program: Program,
    max_as_to_generate_foreach_program: int,
    clingo_arguments: list[str],
    empty_score: float,
) -> Callable[[list[str]], tuple[float, bool, list[int]]]:
    cache: dict[tuple[str, ...], CachedFitnessResult] = {}
    solver = ClingoInterface(
        program.background,
        [f"{max_as_to_generate_foreach_program}", *clingo_arguments],
    )

    def evaluate_score(
        candidate_program: list[str],
    ) -> tuple[float, bool, list[int]]:
        return cached_fitness(
            cache,
            candidate_program,
            lambda: _evaluate_score(
                program,
                candidate_program,
                solver,
                empty_score,
            ),
        )

    return evaluate_score


def _evaluate_score(
    program: Program,
    candidate_program: list[str],
    solver: ClingoInterface,
    empty_score: float,
) -> FitnessResult:
    cov = solver.extract_coverage_and_set_clauses(
        candidate_program,
        program.positive_examples,
        program.negative_examples,
        False,
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
