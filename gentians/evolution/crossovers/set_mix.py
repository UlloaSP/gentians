from ..context import EvolutionContext
from ...hypotheses import Genome
from ..variation import cross


class SetMixCrossover:
    def __init__(self, probability: float) -> None:
        if isinstance(probability, bool) or not 0.0 <= probability <= 1.0:
            raise ValueError("crossover probability must be between 0 and 1")
        self.probability = probability

    def __call__(
        self, first: Genome, second: Genome, context: EvolutionContext
    ) -> Genome | None:
        if context.rng.random() >= self.probability:
            return None
        return cross(first, second, context)
