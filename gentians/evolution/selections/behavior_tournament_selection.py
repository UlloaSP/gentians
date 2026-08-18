import math
import random

from ..individual import Individual


class BehaviorTournamentSelection:
    def __init__(self, percentage: float) -> None:
        if not 0.0 < percentage <= 1.0:
            raise ValueError(
                "tournament_percentage must be greater than 0 and at most 1"
            )
        self.percentage = percentage

    def __call__(
        self, population: list[Individual], rng: random.Random
    ) -> tuple[Individual, Individual]:
        size = min(
            len(population),
            max(2, math.ceil(len(population) * self.percentage)),
        )
        sampled = rng.sample(population, size)
        most_positive = max(item.behavior[0].bit_count() for item in sampled)
        first = rng.choice(
            [item for item in sampled if item.behavior[0].bit_count() == most_positive]
        )
        remaining = [item for item in sampled if item is not first]
        if not remaining:
            return first, first

        fewest_negative = min(item.behavior[1].bit_count() for item in remaining)
        return first, rng.choice(
            [
                item
                for item in remaining
                if item.behavior[1].bit_count() == fewest_negative
            ]
        )
