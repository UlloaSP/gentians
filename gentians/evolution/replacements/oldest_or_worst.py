import math
import random
from collections import Counter

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

    With ``behavior_tiebreak`` enabled, a candidate tied with the worst score
    and carrying a behavior absent from the population bypasses the random
    policy. It evicts the oldest worst-scoring member of the most frequent
    behavior, preserving fitness while increasing behavioral diversity.

    Accepted replacements return a new score-sorted list with the same size.
    Rejected candidates return the supplied population unchanged.
    """

    def __init__(
        self, probability: float, behavior_tiebreak: bool = False
    ) -> None:
        # Expected range is [0, 1]: 0 always targets the worst, 1 first tries
        # the oldest. Intermediate values trade exploitation for turnover.
        self.probability = probability
        self.behavior_tiebreak = behavior_tiebreak

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
            any(item.program == candidate.program for item in population)
            or not math.isfinite(candidate.score)
            or population
            and candidate.score < population[-1].score
        ):
            return population

        # Work on a copy. Besides locating the worst member, sorting restores
        # the ordering contract before the updated population reaches callers.
        ranked = sorted(population, key=lambda item: item.score, reverse=True)
        worst_score = ranked[-1].score

        # Behavioral diversity is only a tie-break. Restricting victims to the
        # worst score prevents diversity from sacrificing a fitter individual.
        # The candidate must introduce a new behavior; otherwise normal
        # oldest-or-worst replacement remains the intended policy.
        if (
            self.behavior_tiebreak
            and candidate.score == worst_score
            and all(item.behavior != candidate.behavior for item in ranked)
        ):
            worst = [item for item in ranked if item.score == worst_score]
            frequencies = Counter(item.behavior for item in ranked)

            # Remove from the behavior occupying the most population slots.
            # If several eligible members share that behavior frequency, age
            # breaks the tie so long-lived material yields to the newcomer.
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
            # Lower timestamps are older. The injected RNG makes this policy
            # reproducible under the search's configured random seed.
            victim = (
                min(ranked, key=lambda item: item.generated_timestamp)
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
