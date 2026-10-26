import math
import random

from ...evaluation.result import dominates
from ...hypotheses import program_distance
from ..individual import Individual


class DominatedOrWorstReplacement:
    """Replace an individual whose coverage the candidate subsumes.

    Fitness is maximized. The input population must be non-empty and sorted by
    descending score. A candidate is considered only when it is finite and has
    a novel program.

    The candidate dominates an individual when it covers every positive
    example that individual covers and no negative example that individual
    avoids. Both behaviors come from evaluating complete programs, so this
    compares observed coverage and assumes nothing about clause contributions.
    The score is monotone in coverage, so a dominated individual is never
    fitter than the candidate.

    Among dominated individuals, the victim is the first by: strict dominance
    before equal behavior, lowest score, most similar program, oldest. A
    dominated victim leaves every example's best case result in the population
    intact. When the candidate dominates no one, it replaces the worst
    individual if it is at least as fit, as in score-based replacement.

    Accepted replacements return a new score-sorted list with the same size.
    Rejected candidates return the supplied population unchanged.
    """

    def __call__(
        self,
        population: list[Individual],
        candidate: Individual,
        rng: random.Random,
    ) -> list[Individual]:
        if (
            any(item.genome == candidate.genome for item in population)
            or not math.isfinite(candidate.score)
        ):
            return population

        ranked = sorted(population, key=lambda item: item.score, reverse=True)
        if not ranked:
            return population
        dominated = [item for item in ranked if dominates(candidate.behavior, item.behavior)]
        if dominated:
            victim = min(dominated, key=lambda item: (
                dominates(item.behavior, candidate.behavior),
                item.score,
                program_distance(item.genome, candidate.genome),
                item.birth_order,
            ))
        elif candidate.score >= ranked[-1].score:
            victim = ranked[-1]
        else:
            return population

        ranked.remove(victim)
        ranked.append(candidate)
        return sorted(ranked, key=lambda item: item.score, reverse=True)

