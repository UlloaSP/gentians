from typing import Any

from ...asp.normal_coverage_solver import NormalCoverageSolver
from ...rule_generation.program import Program
from ..types import FitnessResult
from .coverage_common import coverage_score, record_fitness_metric


class CovProgram:
    def __init__(self, program: Program, solver: NormalCoverageSolver) -> None:
        self.program = program
        self.solver = solver

    @classmethod
    def from_config(cls, program: Program, config: dict[str, Any]):
        values = iter(str(value) for value in config.get("clingo_arguments", []))
        extra = []
        for value in values:
            if value == "--enum-mode":
                next(values, None)
            elif not value.startswith("--enum-mode="):
                extra.append(value)
        return cls(
            program,
            NormalCoverageSolver(
                program.background,
                ["0", "--enum-mode=brave", *extra],
                program.positive_examples,
                program.negative_examples,
            ),
        )

    def __call__(self, candidate: tuple[str, ...]) -> FitnessResult:
        coverage = self.solver.extract_fixed_coverage(candidate)
        score = coverage_score(self.program, coverage)
        best_found = (
            coverage.pos_mask.bit_count() == len(self.program.positive_examples)
            and coverage.neg_mask == 0
        )
        record_fitness_metric(self.program, candidate, coverage, score, best_found)
        return FitnessResult(score, best_found, (coverage.pos_mask, coverage.neg_mask))
