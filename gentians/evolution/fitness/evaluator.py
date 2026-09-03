from collections.abc import Callable

from ...asp.coverage import Coverage
from ...asp.normal_coverage_solver import NormalCoverageSolver
from ...language.asp import AspProgram
from ...language.ir.inductive_task import InductiveTask
from ..types import FitnessResult
from .metrics import record_fitness_metric


class FitnessEvaluator:
    def __init__(
        self,
        task: InductiveTask,
        solver: NormalCoverageSolver,
        score: Callable[[InductiveTask, Coverage], float],
    ) -> None:
        self.task = task
        self.solver = solver
        self.score = score

    def __call__(self, candidate: AspProgram) -> FitnessResult:
        coverage = self.solver.extract_fixed_coverage(candidate)
        score = self.score(self.task, coverage)
        is_solution = (
            coverage.pos_mask.bit_count() == len(self.task.positive_examples)
            and coverage.neg_mask == 0
        )
        record_fitness_metric(self.task, candidate, coverage, score, is_solution)
        return FitnessResult(
            score,
            is_solution,
            (coverage.pos_mask, coverage.neg_mask),
        )
