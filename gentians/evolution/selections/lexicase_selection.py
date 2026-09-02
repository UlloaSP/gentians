import random

from ..individual import Individual


class LexicaseSelection:
    def __call__(
        self, population: list[Individual], rng: random.Random
    ) -> tuple[Individual, Individual]:
        return self._one(population, rng), self._one(population, rng)

    @staticmethod
    def _one(population: list[Individual], rng: random.Random) -> Individual:
        positive = 0
        negative = 0
        for item in population:
            positive |= item.behavior[0]
            negative |= item.behavior[1]

        cases = [(bit, True) for bit in _bits(positive)]
        cases.extend((bit, False) for bit in _bits(negative))
        rng.shuffle(cases)

        candidates = population
        for bit, should_cover in cases:
            passing = [
                item
                for item in candidates
                if bool(item.behavior[0 if should_cover else 1] & bit) == should_cover
            ]
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
