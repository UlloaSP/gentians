"""Generation and epoch accounting for incremental search."""

from ..timing import instrumentation, metric_enabled, net_time, record_ga_generation, record_metric
from .incremental_population import IncrementalPopulation


class IncrementalProgress:
    def __init__(self) -> None:
        self.started = net_time()
        self.epoch = 0
        self.epoch_started = 0
        self.epoch_evaluations = 0
        self.duplicates = 0

    def generation(self, generation: int, population: IncrementalPopulation) -> None:
        record_ga_generation(
            generation, population.best.score, population.members,
            elapsed_seconds=net_time() - self.started,
            fitness_evaluations=population.candidates.evaluations,
        )

    def end_epoch(self, generation: int, reason: str, population: IncrementalPopulation) -> None:
        if metric_enabled("incremental"):
            with instrumentation():
                record_metric("incremental", {
                    "epoch": self.epoch,
                    "reason": reason,
                    "active_clauses": population.candidates.hypotheses.available_clauses.bit_count(),
                    "build_seconds": population.build_seconds,
                    "generations": generation - self.epoch_started,
                    "evaluations": population.candidates.evaluations - self.epoch_evaluations,
                    "duplicates": self.duplicates,
                    "best_score": population.best.score,
                })

    def next_epoch(self, generation: int, reason: str, population: IncrementalPopulation) -> None:
        self.end_epoch(generation, reason, population)
        self.epoch += 1
        self.epoch_started = generation
        self.epoch_evaluations = population.candidates.evaluations
        self.duplicates = 0
