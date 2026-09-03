from typing import Any

from ...asp.normal_coverage_solver import NormalCoverageSolver
from ...language.ir.inductive_task import InductiveTask
from ..types import FitnessResult
from .coverage_common import coverage_score, record_fitness_metric


class CovProgram:
    def __init__(self, task: InductiveTask, solver: NormalCoverageSolver) -> None:
        self.task = task
        self.solver = solver

    @classmethod
    def from_config(cls, task: InductiveTask, config: dict[str, Any]):
        values = iter(str(value) for value in config.get("clingo_arguments", []))
        extra = []
        for value in values:
            if value == "--enum-mode":
                next(values, None)
            elif not value.startswith("--enum-mode="):
                extra.append(value)
        return cls(
            task,
            NormalCoverageSolver(
                task.background,
                ["0", "--enum-mode=brave", *extra],
                task.positive_examples,
                task.negative_examples,
            ),
        )

    def __call__(self, candidate: tuple[str, ...]) -> FitnessResult:
        coverage = self.solver.extract_fixed_coverage(candidate)
        score = coverage_score(self.task, coverage)
        best_found = (
            coverage.pos_mask.bit_count() == len(self.task.positive_examples)
            and coverage.neg_mask == 0
        )
        record_fitness_metric(self.task, candidate, coverage, score, best_found)
        return FitnessResult(score, best_found, (coverage.pos_mask, coverage.neg_mask))
