from collections.abc import Callable

from ..language.asp import AspProgram
from ..language.ir.inductive_task import InductiveTask
from .coverage import Coverage
from .metrics import record_evaluation_metric
from .pool_solver import EpochPoolCoverageSolver
from .result import EvaluationResult
from .solver import CoverageSolver


class CandidateEvaluator:
    def __init__(
        self,
        task: InductiveTask,
        solver: CoverageSolver | EpochPoolCoverageSolver,
        score: Callable[[InductiveTask, Coverage], float],
        *,
        constraint_diagnosis: bool = False,
    ) -> None:
        self.task = task
        self.solver = solver
        self.score = score
        self.constraint_diagnosis = constraint_diagnosis

    def __call__(self, candidate: AspProgram) -> EvaluationResult:
        coverage = self.solver.extract_coverage(candidate)
        score = self.score(self.task, coverage)
        is_complete = coverage.pos_mask.bit_count() == len(
            self.task.positive_examples
        )
        is_consistent = coverage.neg_mask == 0
        is_solution = is_complete and is_consistent
        potential = None
        potential_complete = None
        if self.constraint_diagnosis:
            assert isinstance(self.solver, CoverageSolver)
            potential = self.solver.positive_ceiling(candidate, coverage)
            potential_complete = potential.bit_count() == len(self.task.positive_examples)
        record_evaluation_metric(
            self.task,
            candidate,
            coverage,
            score,
            is_solution,
            is_complete,
            is_consistent,
            potential,
            potential_complete,
        )
        return EvaluationResult(
            score,
            is_solution,
            (coverage.pos_mask, coverage.neg_mask),
            is_complete,
            is_consistent,
            potential,
            potential_complete,
        )
