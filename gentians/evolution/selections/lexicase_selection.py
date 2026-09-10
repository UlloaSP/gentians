import random

from ..individual import Individual


class LexicaseSelection:
    def __call__(
        self,
        population: list[Individual],
        count: int,
        rng: random.Random,
    ) -> list[Individual]:
        if not population:
            raise ValueError("Population must not be empty")

        if count < 0:
            raise ValueError("Count must be non-negative")

        # The population does not change between draws, so the available
        # lexicase cases only need to be computed once.
        cases = self._cases(population)

        # Each draw independently shuffles the cases and selection is performed
        # with replacement, so the same individual may be selected more than once.
        return [self._select_one(population, cases, rng) for _ in range(count)]

    @staticmethod
    def _cases(
        population: list[Individual],
    ) -> tuple[tuple[int, bool], ...]:
        # behavior[0] contains the covered positive examples as a bit mask.
        # behavior[1] contains the covered negative examples as a bit mask.
        positive_mask = 0
        negative_mask = 0

        # Only examples present in at least one individual's behavior can
        # distinguish individuals during selection.
        for individual in population:
            positive_mask |= individual.behavior[0]
            negative_mask |= individual.behavior[1]

        # Positive cases prefer individuals that cover the example.
        # Negative cases prefer individuals that do not cover the example.
        return (
            *((bit, True) for bit in _bits(positive_mask)),
            *((bit, False) for bit in _bits(negative_mask)),
        )

    @staticmethod
    def _select_one(
        population: list[Individual],
        cases: tuple[tuple[int, bool], ...],
        rng: random.Random,
    ) -> Individual:
        candidates = population

        # Lexicase requires a new random case order for every parent selection.
        shuffled_cases = list(cases)
        rng.shuffle(shuffled_cases)

        for bit, should_cover in shuffled_cases:
            # Positive cases inspect behavior[0], while negative cases inspect
            # behavior[1].
            behavior_index = 0 if should_cover else 1

            # For a positive case, keep candidates that cover it.
            # For a negative case, keep candidates that do not cover it.
            passing = [
                individual
                for individual in candidates
                if bool(individual.behavior[behavior_index] & bit) == should_cover
            ]

            # If nobody satisfies the case, it cannot discriminate among the
            # remaining candidates, so the current candidate set is preserved.
            if passing:
                candidates = passing

                # Once only one candidate remains, later cases cannot change
                # the result.
                if len(candidates) == 1:
                    return candidates[0]

        # Multiple candidates may remain if they are indistinguishable under
        # all processed cases. Break the tie uniformly at random.
        return rng.choice(candidates)


def _bits(mask: int):
    """Yield each set bit of an integer mask independently."""
    while mask:
        # Two's-complement trick that isolates the least significant set bit.
        bit = mask & -mask
        yield bit

        # Remove the bit that has just been yielded.
        mask ^= bit
