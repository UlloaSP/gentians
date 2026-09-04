import math
import random

from ..individual import Individual


class OldestOrWorstReplacement:
    """Replace one individual without lowering the population's fitness.

    Fitness is maximized. The input population must be non-empty and sorted by
    descending score, so its last item is the current worst individual. A
    candidate is admitted only when it is finite, has a novel program, and is
    at least as fit as that worst individual.

    ``probability`` controls the replacement policy. A successful random draw
    selects the oldest individual; a failed draw selects the worst. If the
    oldest is fitter than the candidate, the worst is selected instead. This
    fallback keeps age-based turnover from reducing population fitness.

    Accepted replacements return a new score-sorted list with the same size.
    Rejected candidates return the supplied population unchanged.
    """

    def __init__(self, probability: float) -> None:
        if isinstance(probability, bool) or not 0.0 <= probability <= 1.0:
            raise ValueError("replacement probability must be between 0 and 1")
        self.probability = probability

    def __call__(
        self,
        population: list[Individual],
        candidate: Individual,
        rng: random.Random,
    ) -> list[Individual]:
        # Duplicates add no genetic material. NaN and infinities cannot be
        # ranked reliably. A candidate below the admission threshold cannot
        # replace anyone without decreasing the population's score profile.
        if (
            any(item.genome == candidate.genome for item in population)
            or not math.isfinite(candidate.score)
            or population
            and candidate.score < population[-1].score
        ):
            return population

        # Work on a copy. Besides locating the worst member, sorting restores
        # the ordering contract before the updated population reaches callers.
        ranked = sorted(population, key=lambda item: item.score, reverse=True)
        # Lower birth orders are older. The injected RNG makes this policy
        # reproducible under the search's configured random seed.
        victim = (
            min(ranked, key=lambda item: item.birth_order)
            if rng.random() < self.probability
            else ranked[-1]
        )

        # An age-selected victim may be better than the admitted candidate.
        # Fall back to the worst member to retain elitism and population size.
        if victim.score > candidate.score:
            victim = ranked[-1]

        ranked.remove(victim)
        ranked.append(candidate)
        return sorted(ranked, key=lambda item: item.score, reverse=True)
