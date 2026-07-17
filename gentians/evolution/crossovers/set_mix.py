from __future__ import annotations

from ..evolution_context import EvolutionContext
from ..types import Genome


class SetMixCrossover:
    def __init__(self, probability: float) -> None:
        self.probability = probability

    def __call__(
        self, first: Genome, second: Genome, context: EvolutionContext
    ) -> tuple[Genome, ...]:
        if context.rng.random() >= self.probability:
            return ()
        children = (
            context.generator.mix(first, second, 0.7, 0.3),
            context.generator.mix(first, second, 0.3, 0.7),
        )
        return tuple(child for child in children if child is not None)
