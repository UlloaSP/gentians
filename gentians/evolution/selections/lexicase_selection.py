import random

from ..individual import Individual


class LexicaseSelection:
    def __call__(
        self, population: list[Individual], count: int, rng: random.Random
    ) -> list[Individual]:
        # Each draw shuffles its own cases and may select the same parent again.
        return [self._one(population, rng) for _ in range(count)]

    def _one(self, population: list[Individual], rng: random.Random) -> Individual:
        # Cases absent from every coverage mask cannot distinguish individuals.
        positive = 0
        negative = 0
        for item in population:
            positive |= item.behavior[0]
            negative |= item.behavior[1]

        cases = [(bit, True) for bit in _bits(positive)]
        cases.extend((bit, False) for bit in _bits(negative))
        rng.shuffle(cases)

        # Prefer covering positives and avoiding negatives, in shuffled case order.
        candidates = population
        for bit, should_cover in cases:
            passing = [
                item
                for item in candidates
                if bool(item.behavior[0 if should_cover else 1] & bit) == should_cover
            ]
            # Keep the current candidates when none passes this case.
            if passing:
                candidates = passing
            if len(candidates) == 1:
                return candidates[0]
        return rng.choice(candidates)


def _bits(mask: int):
    while mask:
        bit = mask & -mask
        yield bit
        mask ^= bit
