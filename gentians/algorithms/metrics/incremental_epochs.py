"""Epoch accounting for incremental search."""

from ...search.clause_pool import IncrementalClausePool
from ...search.population import Population
from ...timing import instrumentation, metric_enabled, record_metric


class EpochMetrics:
    """Record one row per epoch: why it ended and what it cost."""

    def __init__(self, pool: IncrementalClausePool) -> None:
        self.pool = pool
        self.epoch = 0
        self.epoch_started = 0
        self.epoch_evaluations = 0
        self.epoch_build_seconds = 0.0
        self.duplicates = 0

    def end(self, generation: int, reason: str, population: Population) -> None:
        if metric_enabled("incremental"):
            with instrumentation():
                record_metric("incremental", {
                    "epoch": self.epoch,
                    "reason": reason,
                    "active_clauses": population.candidates.hypotheses.available_clauses.bit_count(),
                    "build_seconds": self.pool.build_seconds - self.epoch_build_seconds,
                    "generations": generation - self.epoch_started,
                    "evaluations": population.candidates.evaluations - self.epoch_evaluations,
                    "duplicates": self.duplicates,
                    "best_score": population.best.score,
                })

    def next(self, generation: int, reason: str, population: Population) -> None:
        self.end(generation, reason, population)
        self.epoch += 1
        self.epoch_started = generation
        self.epoch_evaluations = population.candidates.evaluations
        self.epoch_build_seconds = self.pool.build_seconds
        self.duplicates = 0
