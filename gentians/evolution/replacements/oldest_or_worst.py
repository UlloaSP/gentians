import math
import random

from ..individual import Individual


class OldestOrWorstReplacement:
    """Score-based replacement with an optional complete-candidate reserve.

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

    With ``complete_quota > 0``, filling a missing complete slot may lower
    fitness except for the best individual. The best complete members are
    protected up to the quota, capped at population size minus one. This does
    not generate complete candidates or guarantee their selection as parents.
    """

    def __init__(self, probability: float, complete_quota: int = 0) -> None:
        if isinstance(probability, bool) or not 0.0 <= probability <= 1.0:
            raise ValueError("replacement probability must be between 0 and 1")
        self.probability = probability
        if type(complete_quota) is not int or complete_quota < 0:
            raise ValueError("complete_quota must be a non-negative integer")
        self.complete_quota = complete_quota

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
        ):
            return population

        # Work on a copy. Besides locating the worst member, sorting restores
        # the ordering contract before the updated population reaches callers.
        ranked = sorted(population, key=lambda item: item.score, reverse=True)
        quota = min(self.complete_quota, max(0, len(ranked) - 1))
        protected = [item for item in ranked if item.is_complete][:quota]
        if candidate.is_complete and len(protected) < quota:
            # Recover a missing reserve slot even at lower fitness, but never
            # sacrifice the current best or an already complete individual.
            victim = next(item for item in reversed(ranked[1:]) if not item.is_complete)
            ranked.remove(victim)
            return sorted([*ranked, candidate], key=lambda item: item.score, reverse=True)
        eligible = [item for item in ranked if item not in protected
                    or candidate.is_complete and candidate.score >= item.score]
        if not eligible or candidate.score < eligible[-1].score:
            return population
        # Lower birth orders are older. The injected RNG makes this policy
        # reproducible under the search's configured random seed.
        victim = (
            min(eligible, key=lambda item: item.birth_order)
            if rng.random() < self.probability
            else eligible[-1]
        )

        # An age-selected victim may be better than the admitted candidate.
        # Fall back to the worst member to retain elitism and population size.
        if victim.score > candidate.score:
            victim = eligible[-1]

        ranked.remove(victim)
        ranked.append(candidate)
        return sorted(ranked, key=lambda item: item.score, reverse=True)
