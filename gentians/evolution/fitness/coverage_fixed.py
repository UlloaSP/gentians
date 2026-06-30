from collections.abc import Callable
import math
import re
from .coverage_common import (
    CachedFitnessResult,
    cached_fitness,
    FitnessResult,
    coverage_rates,
    record_fitness_metric,
)
from ...asp.clingo import ClingoInterface
from ...rule_generation.parser import split_top_level_args
from ...rule_generation.program import Program
from ...rule_generation.rule_space import RuleId, RuleSpace


def coverage_fixed(
    program: Program,
    max_as_to_generate_foreach_program: int,
    clingo_arguments: list[str],
    empty_score: float,
    size_penalty: float,
    literal_penalty: float,
    redundancy_penalty: float,
    rule_space: RuleSpace,
) -> Callable[[list[RuleId]], tuple[float, bool, list[int]]]:
    cache: dict[tuple[RuleId, ...], CachedFitnessResult] = {}
    normal_solver = ClingoInterface(
        program.background,
        ["1", *clingo_arguments],
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
                empty_score,
                size_penalty,
                literal_penalty,
                redundancy_penalty,
            ),
        )

    return evaluate_score


def _evaluate_score(
    program: Program,
    candidate_program: list[RuleId],
    rule_space: RuleSpace,
    normal_solver: ClingoInterface,
    empty_score: float,
    size_penalty: float,
    literal_penalty: float,
    redundancy_penalty: float,
) -> FitnessResult:
    indexes = list(range(len(candidate_program)))
    rendered_program = rule_space.render(candidate_program)
    complexity = _program_complexity(rendered_program)
    size_cost = (
        len(candidate_program) * size_penalty
        + complexity.body_literals * literal_penalty
        + complexity.redundancies * redundancy_penalty
    )

    coverage = normal_solver.extract_example_assumption_coverage(
        rendered_program,
        program.positive_examples,
        program.negative_examples,
    )
    covered_positive = coverage.pos_mask.bit_count()
    has_negative_violation = bool(coverage.neg_mask)
    positive_rate = (
        covered_positive / len(program.positive_examples)
        if program.positive_examples
        else 1.0
    )
    negative_rate = (
        coverage.neg_mask.bit_count() / len(program.negative_examples)
        if program.negative_examples
        else 0.0
    )
    if covered_positive == 0 and not has_negative_violation and program.positive_examples:
        score = 1.0
    else:
        score = math.exp(5 * (3 * positive_rate - negative_rate - size_cost))
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


class _ProgramComplexity:
    def __init__(self, body_literals: int, redundancies: int) -> None:
        self.body_literals = body_literals
        self.redundancies = redundancies


def _program_complexity(program: list[str]) -> _ProgramComplexity:
    body_literals = 0
    redundancies = 0
    for clause in program:
        literals = _body_literals(clause)
        body_literals += len(literals)
        redundancies += _redundancy_count(literals)
    return _ProgramComplexity(body_literals, redundancies)


def _body_literals(clause: str) -> list[str]:
    content = clause.strip().rstrip(".")
    if ":-" not in content:
        return []
    _, body = content.split(":-", 1)
    return [_normalize_literal(literal) for literal in split_top_level_args(body)]


def _normalize_literal(literal: str) -> str:
    return re.sub(r"\s+", "", literal.strip())


def _redundancy_count(literals: list[str]) -> int:
    seen: set[str] = set()
    redundancies = 0
    for literal in literals:
        key = _redundancy_key(literal)
        if key in seen:
            redundancies += 1
        else:
            seen.add(key)
    return redundancies


def _redundancy_key(literal: str) -> str:
    match = re.fullmatch(r"(V\d+)!=(V\d+)", literal)
    if match:
        left, right = sorted(match.groups())
        return f"{left}!={right}"
    return literal
