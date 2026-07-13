from __future__ import annotations

import math
import random

from ..individual import Individual


class OldestOrWorstReplacement:
    def __init__(self, probability: float) -> None:
        self.probability = probability

    def __call__(
        self,
        population: list[Individual],
        candidate: Individual,
        rng: random.Random,
    ) -> list[Individual]:
        if (
            any(item.program == candidate.program for item in population)
            or not math.isfinite(candidate.score)
            or population
            and candidate.score < population[-1].score
        ):
            return population
        ranked = sorted(
            (*population, candidate), key=lambda item: item.score, reverse=True
        )
        victim = (
            min(ranked, key=lambda item: item.generated_timestamp)
            if rng.random() < self.probability
            else ranked[-1]
        )
        if victim.score > candidate.score:
            victim = ranked[-1]
        ranked.remove(victim)
        return ranked
