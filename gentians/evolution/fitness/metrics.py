from ...asp.coverage import Coverage
from ...language.asp import AspProgram
from ...language.ir.inductive_task import InductiveTask
from ...timing import instrumentation, metric_enabled, record_metric


def record_fitness_metric(
    task: InductiveTask,
    candidate: AspProgram,
    coverage: Coverage,
    score: float,
    is_solution: bool,
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
                "covered_positive": coverage.pos_mask.bit_count(),
                "covered_negative": coverage.neg_mask.bit_count(),
                "total_positive": len(task.positive_examples),
                "total_negative": len(task.negative_examples),
            },
        )
