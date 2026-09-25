"""Per-generation search progress shared by both algorithms."""

from ...search.population import Population
from ...timing import net_time, record_ga_generation


class GenerationMetrics:
    """Record the population after each generation, timed from construction.

    A restart marks the next recorded generation, the one it started.
    """

    def __init__(self) -> None:
        self.started = net_time()
        self.restarted = False

    def mark_restart(self) -> None:
        self.restarted = True

    def record(self, generation: int, population: Population) -> None:
        record_ga_generation(
            generation, population.best.score, population.members,
            elapsed_seconds=net_time() - self.started,
            fitness_evaluations=population.candidates.evaluations,
            restarted=self.restarted,
        )
        self.restarted = False
