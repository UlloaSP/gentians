from collections.abc import Callable

from ..language.asp import AspProgram
from ..language.ir.inductive_task import InductiveTask
from .coverage import Coverage
from .metrics import record_evaluation_metric
from .result import EvaluationResult
from .solver import CoverageSolver


class CandidateEvaluator:
    def __init__(
        self,
        task: InductiveTask,
        solver: CoverageSolver,
        score: Callable[[InductiveTask, Coverage], float],
    ) -> None:
        self.task = task
        self.solver = solver
        self.score = score

    def __call__(self, candidate: AspProgram) -> EvaluationResult:
        coverage = self.solver.extract_coverage(candidate)
        score = self.score(self.task, coverage)
        is_solution = (
            coverage.pos_mask.bit_count() == len(self.task.positive_examples)
            and coverage.neg_mask == 0
        )
        record_evaluation_metric(self.task, candidate, coverage, score, is_solution)
        return EvaluationResult(
            score,
            is_solution,
            (coverage.pos_mask, coverage.neg_mask),
        )
