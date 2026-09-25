from ..context import EvolutionContext
from ..individual import Individual


class StagnationRestart:
    """Restart from the champion after a run of generations without improvement.

    The strategy keeps its progress clock across calls, so each search needs a
    fresh instance. Every call observes the champion, including calls where the
    algorithm cannot restart yet. Spaces without headed clauses never restart.
    """

    def __init__(self, generations: int) -> None:
        if not isinstance(generations, int) or isinstance(generations, bool) or generations < 1:
            raise ValueError("restart generations must be a positive integer")
        self.generations = generations
        self.best_score = float("-inf")
        self.last_progress = 0

    def __call__(
        self,
        generation: int,
        population: list[Individual],
        champion: Individual,
        context: EvolutionContext,
        eligible: bool,
    ) -> list[Individual] | None:
        if champion.score > self.best_score:
            self.best_score = champion.score
            self.last_progress = generation
        if (
            not eligible
            or not context.hypotheses.clauses_by_head
            or generation - self.last_progress < self.generations
        ):
            return None
        self.last_progress = generation
        return [champion]
