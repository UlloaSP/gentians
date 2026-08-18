import math
import random
from collections import Counter

from ..individual import Individual


class OldestOrWorstReplacement:
    def __init__(
        self, probability: float, behavior_tiebreak: bool = False
    ) -> None:
        self.probability = probability
        self.behavior_tiebreak = behavior_tiebreak

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
        ranked = sorted(population, key=lambda item: item.score, reverse=True)
        worst_score = ranked[-1].score
        if (
            self.behavior_tiebreak
            and candidate.score == worst_score
            and all(item.behavior != candidate.behavior for item in ranked)
        ):
            worst = [item for item in ranked if item.score == worst_score]
            frequencies = Counter(item.behavior for item in ranked)
            crowded = max(frequencies[item.behavior] for item in worst)
            victim = min(
                (
                    item
                    for item in worst
                    if frequencies[item.behavior] == crowded
                ),
                key=lambda item: item.generated_timestamp,
            )
        else:
            victim = (
                min(ranked, key=lambda item: item.generated_timestamp)
                if rng.random() < self.probability
                else ranked[-1]
            )
        if victim.score > candidate.score:
            victim = ranked[-1]
        ranked.remove(victim)
        ranked.append(candidate)
        return sorted(ranked, key=lambda item: item.score, reverse=True)
