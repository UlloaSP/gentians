from __future__ import annotations

import random

from ..individual import Individual


class TournamentSelection:
    def __init__(self, size: int, probability: float) -> None:
        self.size = size
        self.probability = probability

    def __call__(
        self, population: list[Individual], rng: random.Random
    ) -> tuple[Individual, Individual]:
        return self._one(population, rng), self._one(population, rng)

    def _one(self, population: list[Individual], rng: random.Random) -> Individual:
        ranked = sorted(
            rng.sample(population, min(self.size, len(population))),
            key=lambda item: item.score,
            reverse=True,
        )
        while len(ranked) > 1 and rng.random() > self.probability:
            ranked.pop(0)
        return ranked[0]
