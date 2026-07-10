from collections.abc import Callable
import math

from .coverage_common import cached_fitness, record_fitness_metric
from ...asp.clingo import ClingoInterface
from ...asp.coverage import Coverage
from ...rule_generation.program import Program


def coverage_original(
    program: Program,
    max_as_to_generate_foreach_program: int,
    clingo_arguments: list[str],
) -> Callable[[tuple[str, ...]], tuple[float, bool, tuple[str, ...] | None]]:
    cache: dict[tuple[str, ...], tuple[float, bool, tuple[str, ...] | None]] = {}
    solver = ClingoInterface(
        program.background,
        [f"{max_as_to_generate_foreach_program}", "--project", *clingo_arguments],
        program.positive_examples,
        program.negative_examples,
    )

    def evaluate_score(
        candidate_program: tuple[str, ...],
    ) -> tuple[float, bool, tuple[str, ...] | None]:
        return cached_fitness(
            cache,
            candidate_program,
            lambda cached_program: _evaluate_score(program, cached_program, solver),
        )

    return evaluate_score


def _evaluate_score(
    program: Program,
    candidate_program: tuple[str, ...],
    solver: ClingoInterface,
) -> tuple[float, bool, tuple[str, ...] | None]:
    coverages = solver.extract_subset_coverage(candidate_program)
    if coverages is None:
        record_fitness_metric(
            "coverage_original",
            program,
            candidate_program,
            Coverage([], []),
            -2000.0,
            False,
        )
        return -2000.0, False, None

    scores: list[float] = []
    best_subsets: list[tuple[int, ...]] = []
    best_coverage = Coverage([], [])
    best_score = float("-inf")
    for selected, coverage in coverages.items():
        covered_positive = coverage.pos_mask.bit_count()
        covered_negative = coverage.neg_mask.bit_count()
        positive_rate = (
            covered_positive / len(program.positive_examples)
            if program.positive_examples
            else 0.0
        )
        negative_rate = (
            covered_negative / len(program.negative_examples)
            if program.negative_examples
            else 0.0
        )
        subset_score = math.exp((positive_rate - negative_rate) * 10)
        scores.append(subset_score)
        if subset_score > best_score:
            best_score = subset_score
            best_coverage = coverage
        if (
            covered_positive == len(program.positive_examples)
            and covered_negative == 0
        ):
            best_subsets.append(selected)

    score = mean(scores) if scores else -2000.0
    best_subsets.sort(key=len)
    best_program = (
        tuple(candidate_program[index] for index in best_subsets[0])
        if best_subsets
        else None
    )
    best_found = best_program is not None
    record_fitness_metric(
        "coverage_original",
        program,
        best_program or candidate_program,
        best_coverage,
        score,
        best_found,
    )
    return score, best_found, best_program


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
