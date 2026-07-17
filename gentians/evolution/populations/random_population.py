from __future__ import annotations

from ..evolution_context import EvolutionContext
from ..types import Genome


class RandomPopulation:
    def __init__(self, size: int) -> None:
        self.size = size

    def __call__(self, context: EvolutionContext) -> list[Genome]:
        return [
            genome
            for _ in range(self.size)
            if (genome := context.generator.create()) is not None
        ]
