from ..language.ir.inductive_task import InductiveTask
from ..timing import instrumentation, metric_enabled, record_metric
from .clause_space import ClauseSpace


def record_clause_space(task: InductiveTask, space: ClauseSpace) -> None:
    if not metric_enabled("candidate"):
        return
    invented = set(task.invented_predicates)
    with instrumentation():
        record_metric(
            "candidate",
            {
                "metric": "clause_generation",
                "clauses": len(space),
                "invented_predicates": len(invented),
                "invented_definition_clauses": sum(
                    bool(entry.heads & invented) for entry in space.entries
                ),
                "invented_consumer_clauses": sum(
                    bool(entry.deps & invented) for entry in space.entries
                ),
            },
        )
