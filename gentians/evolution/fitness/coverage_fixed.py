from collections.abc import Callable
from functools import lru_cache
import math
import re
from .coverage_common import (
    CachedFitnessResult,
    cached_fitness,
    FitnessResult,
    record_fitness_metric,
)
from ...asp.clingo import ClingoInterface
from ...rule_generation.parser import split_top_level_args
from ...rule_generation.program import Program


def coverage_fixed(
    program: Program,
    max_as_to_generate_foreach_program: int,
    clingo_arguments: list[str],
    size_penalty: float,
    literal_penalty: float,
    redundancy_penalty: float,
) -> Callable[[list[str]], tuple[float, bool]]:
    cache: dict[tuple[str, ...], CachedFitnessResult] = {}
    normal_solver = ClingoInterface(
        program.background,
        [f"{max_as_to_generate_foreach_program}", *clingo_arguments],
    )

    def evaluate_score(
        candidate_program: list[str],
    ) -> tuple[float, bool]:
        return cached_fitness(
            cache,
            candidate_program,
            lambda cached_program: _evaluate_score(
                program=program,
                candidate_program=cached_program,
                normal_solver=normal_solver,
                size_penalty=size_penalty,
                literal_penalty=literal_penalty,
                redundancy_penalty=redundancy_penalty,
            ),
        )

    return evaluate_score


def _evaluate_score(
    program: Program,
    candidate_program: list[str],
    normal_solver: ClingoInterface,
    size_penalty: float,
    literal_penalty: float,
    redundancy_penalty: float,
) -> FitnessResult:
    body_literals, redundancies = _program_complexity(candidate_program)
    size_cost = (
        len(candidate_program) * size_penalty
        + body_literals * literal_penalty
        + redundancies * redundancy_penalty
    )

    coverage = normal_solver.extract_fixed_coverage(
        candidate_program,
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
    record_fitness_metric(
        "coverage_fixed",
        program,
        candidate_program,
        coverage,
        score,
        best_found,
    )
    return score, best_found


def _program_complexity(program: list[str]) -> tuple[int, int]:
    body_literals = 0
    redundancies = 0
    for clause in program:
        literals = _body_literals(clause)
        body_literals += len(literals)
        redundancies += _redundancy_count(literals)
    return body_literals, redundancies


@lru_cache(maxsize=None)
def _body_literals(clause: str) -> tuple[str, ...]:
    content = clause.strip().rstrip(".")
    if ":-" not in content:
        return ()
    _, body = content.split(":-", 1)
    return tuple(_normalize_literal(literal) for literal in split_top_level_args(body))


def _normalize_literal(literal: str) -> str:
    return re.sub(r"\s+", "", literal.strip())


def _redundancy_count(literals: tuple[str, ...]) -> int:
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
