from ..language.asp import AspProgram
from ..language.ir.inductive_task import InductiveTask
from ..timing import instrumentation, metric_enabled, record_metric
from .coverage import Coverage


def record_evaluation_metric(
    task: InductiveTask,
    candidate: AspProgram,
    coverage: Coverage,
    score: float,
    is_solution: bool,
    is_complete: bool,
    is_consistent: bool,
    potential_pos_mask: int | None = None,
    potential_complete: bool | None = None,
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
                "potential_positive": potential_pos_mask.bit_count() if potential_pos_mask is not None else None,
                "potential_complete": potential_complete,
            },
        )
