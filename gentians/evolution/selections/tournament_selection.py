import math
import random

from ..individual import Individual


class TournamentSelection:
    def __init__(self, percentage: float, probability: float) -> None:
        if isinstance(percentage, bool) or not 0.0 < percentage <= 1.0:
            raise ValueError(
                "tournament_percentage must be greater than 0 and at most 1"
            )
        if isinstance(probability, bool) or not 0.0 <= probability <= 1.0:
            raise ValueError("prob_selecting_fittest must be between 0 and 1")
        self.percentage = percentage
        self.probability = probability

    def __call__(
        self, population: list[Individual], rng: random.Random
    ) -> tuple[Individual, Individual]:
        return self._one(population, rng), self._one(population, rng)

    def _one(self, population: list[Individual], rng: random.Random) -> Individual:
        size = max(1, math.ceil(len(population) * self.percentage))
        ranked = sorted(
            rng.sample(population, size),
            key=lambda item: item.score,
            reverse=True,
        )
        while len(ranked) > 1 and rng.random() > self.probability:
            ranked.pop(0)
        return ranked[0]
