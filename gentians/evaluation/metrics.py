import os
from pathlib import Path

from ..language.asp import AspProgram, render_program
from ..language.ir.inductive_task import InductiveTask
from ..timing import instrumentation, metric_enabled, record_metric
from .coverage import Coverage


class HypothesisCheckpoint:
    """Persist completed improvements, including evaluations during initialization."""

    def __init__(self) -> None:
        self.path = os.environ.get("GENTIANS_HYPOTHESIS_PATH")
        self.best: tuple[bool, float] | None = None

    def record(self, candidate: AspProgram, score: float, is_solution: bool) -> None:
        if not self.path:
            return
        rank = is_solution, score
        if self.best is not None and rank <= self.best:
            return
        with instrumentation():
            path = Path(self.path)
            temporary = path.with_name(path.name + ".tmp")
            temporary.write_text("\n".join(render_program(candidate)) + "\n", encoding="utf-8")
            temporary.replace(path)
            self.best = rank


def record_evaluation_metric(
    task: InductiveTask,
    candidate: AspProgram,
    coverage: Coverage,
    score: float,
    is_solution: bool,
    is_complete: bool,
    is_consistent: bool,
) -> None:
    if not metric_enabled("quality"):
        return
    with instrumentation():
        record_metric(
            "quality",
            {
                "program_size": len(candidate),
                "score": score,
                "best_found": is_solution,
                "complete": is_complete,
                "consistent": is_consistent,
                "covered_positive": coverage.pos_mask.bit_count(),
                "covered_negative": coverage.neg_mask.bit_count(),
                "total_positive": len(task.positive_examples),
                "total_negative": len(task.negative_examples),
            },
        )
