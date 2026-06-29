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
from ...rule_generation.rule_space import RuleId, RuleSpace


def coverage_fixed(
    program: Program,
    max_as_to_generate_foreach_program: int,
    clingo_arguments: list[str],
    empty_score: float,
    size_penalty: float,
    rule_space: RuleSpace,
) -> Callable[[list[RuleId]], tuple[float, bool, list[int]]]:
    cache: dict[tuple[RuleId, ...], CachedFitnessResult] = {}
    normal_solver = ClingoInterface(
        program.background,
        [f"{max_as_to_generate_foreach_program}", *clingo_arguments],
    )
    preground_solver = normal_solver.fixed_coverage_solver(
        rule_space.clauses,
        program.positive_examples,
        program.negative_examples,
    )

    def evaluate_score(
        candidate_program: list[RuleId],
    ) -> tuple[float, bool, list[int]]:
        return cached_fitness(
            cache,
            candidate_program,
            lambda canonical_program: _evaluate_score(
                program,
                canonical_program,
                rule_space,
                normal_solver,
                preground_solver,
                empty_score,
                size_penalty,
            ),
        )

    return evaluate_score


def _evaluate_score(
    program: Program,
    candidate_program: list[RuleId],
    rule_space: RuleSpace,
    normal_solver: ClingoInterface,
    preground_solver,
    empty_score: float,
    size_penalty: float,
) -> FitnessResult:
    indexes = list(range(len(candidate_program)))
    size_cost = len(candidate_program) * size_penalty
    rendered_program = rule_space.render(candidate_program)

    coverage = preground_solver.extract_fixed_coverage_by_id(
        candidate_program,
        stop_on_negative=True,
    )
    if coverage is None:
        coverage = normal_solver.extract_fixed_coverage(
            rendered_program,
            program.positive_examples,
            program.negative_examples,
            stop_on_negative=True,
        )
    covered_positive = coverage.pos_mask.bit_count()
    has_negative_violation = bool(coverage.neg_mask)
    positive_rate = (
        covered_positive / len(program.positive_examples)
        if program.positive_examples
        else 1.0
    )
    negative_rate = 1.0 if has_negative_violation else 0.0
    score = math.exp(7 * (positive_rate - negative_rate - size_cost))
    best_found = (
        covered_positive == len(program.positive_examples)
        and not has_negative_violation
    )
    rates = coverage_rates(program, coverage)
    record_fitness_metric(
        "coverage_fixed",
        program,
        rendered_program,
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
