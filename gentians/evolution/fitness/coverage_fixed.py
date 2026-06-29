from collections.abc import Callable
import math
from .coverage_common import (
    CachedFitnessResult,
    cached_fitness,
    FitnessResult,
    coverage_rates,
    record_fitness_metric,
)
from ...asp.clingo import ClingoInterface
from ...rule_generation.program import Program


def coverage_fixed(
    program: Program,
    max_as_to_generate_foreach_program: int,
    clingo_arguments: list[str],
    empty_score: float,
    size_penalty: float,
) -> Callable[[list[str]], tuple[float, bool, list[int]]]:
    cache: dict[tuple[str, ...], CachedFitnessResult] = {}
    normal_solver = ClingoInterface(
        program.background,
        [f"{max_as_to_generate_foreach_program}", *clingo_arguments],
    )
    brave_solver = ClingoInterface(
        program.background,
        [
            f"{max_as_to_generate_foreach_program}",
            "--enum-mode=brave",
            *clingo_arguments,
        ],
    )

    def evaluate_score(candidate_program: list[str]) -> tuple[float, bool, list[int]]:
        return cached_fitness(
            cache,
            candidate_program,
            lambda canonical_program: _evaluate_score(
                program,
                canonical_program,
                normal_solver,
                brave_solver,
                empty_score,
                size_penalty,
            ),
        )

    return evaluate_score


def _evaluate_score(
    program: Program,
    candidate_program: list[str],
    normal_solver: ClingoInterface,
    brave_solver: ClingoInterface,
    empty_score: float,
    size_penalty: float,
) -> FitnessResult:
    indexes = list(range(len(candidate_program)))
    size_cost = len(candidate_program) * size_penalty

    negative_coverage = normal_solver.extract_fixed_coverage(
        candidate_program,
        [],
        program.negative_examples,
        stop_on_negative=True,
    )
    positive_coverage = brave_solver.extract_fixed_coverage(
        candidate_program,
        program.positive_examples,
        [],
    )
    covered_positive = positive_coverage.pos_mask.bit_count()
    has_negative_violation = bool(negative_coverage.neg_mask)
    positive_rate = (
        covered_positive / len(program.positive_examples)
        if program.positive_examples
        else 1.0
    )
    negative_rate = 1.0 if has_negative_violation else 0.0
    score = math.exp(10 * (2 * positive_rate - negative_rate - size_cost))
    best_found = (
        covered_positive == len(program.positive_examples)
        and not has_negative_violation
    )
    coverage = positive_coverage
    coverage.extend(
        negative_coverage.l_pos,
        negative_coverage.l_neg,
    )
    rates = coverage_rates(program, coverage)
    record_fitness_metric(
        "coverage_fixed",
        program,
        candidate_program,
        {tuple(indexes): coverage},
        [score],
        score,
        empty_score,
        best_found,
        indexes,
        tuple(indexes),
        {tuple(indexes): rates},
    )
    return score, best_found, indexes
