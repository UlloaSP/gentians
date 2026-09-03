from ..context import EvolutionContext
from ...hypotheses import Genome


class SetMixCrossover:
    def __init__(self, probability: float) -> None:
        if isinstance(probability, bool) or not 0.0 <= probability <= 1.0:
            raise ValueError("crossover probability must be between 0 and 1")
        self.probability = probability

    def __call__(
        self, first: Genome, second: Genome, context: EvolutionContext
    ) -> tuple[Genome, ...]:
        if context.rng.random() >= self.probability:
            return ()
        return context.hypotheses.mix(
            first,
            second,
            ((0.7, 0.3), (0.3, 0.7)),
            context.rng,
        )
