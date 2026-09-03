from ..evolution_context import EvolutionContext
from ...hypotheses import Genome


class SetMixCrossover:
    def __init__(self, probability: float) -> None:
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
        )
