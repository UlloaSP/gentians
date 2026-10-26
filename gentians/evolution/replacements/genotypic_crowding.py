import math
import random

from ...hypotheses import program_distance
from ..individual import Individual


class GenotypicCrowdingReplacement:
    """Crowding that compares programs by their clauses.

    Background
    ----------
    A plain genetic algorithm converges to a single region of the search
    space: copies of the fittest program crowd out every other one. Niching
    methods keep several regions ("niches") alive at once, so the population
    can hold different partial solutions in parallel. Crowding (De Jong, 1975,
    "An analysis of the behavior of a class of genetic adaptive systems") is
    the original niching method. Its idea mirrors ecology: a newborn competes
    for a place with the members that resemble it, not with the whole
    population. A new program therefore displaces a similar program, and
    dissimilar programs, which occupy other niches, survive.

    The algorithm
    -------------
    For each offspring:

    1. Draw ``crowding_factor`` (CF) members uniformly at random, without
       repetition, from the current population.
    2. Among them, find the member whose clauses are nearest to the
       offspring's (see "Distance" below).
    3. The offspring replaces that member only if it scores strictly higher.

    De Jong's original step 3 had no fitness test: the offspring always
    entered. With the test, the strategy is what Harik (1995) called
    restricted tournament selection: the offspring holds a tournament against
    its nearest neighbor only. The test makes the replacement elitist, since
    a member is only displaced by a better program, so the best score in the
    population never decreases. A tie keeps the incumbent.

    CF sets how local the competition is. CF = 1 compares the offspring with
    a random member, which is plain random tournament replacement without
    niching. A larger CF makes it more likely that the sample contains the
    offspring's true nearest neighbor, so the offspring competes inside its
    own niche instead of displacing a member of another niche (Mahfoud calls
    the latter a "replacement error"). De Jong used CF = 2 or 3. A CF at least
    the population size always finds the nearest member.

    Distance
    --------
    Genotypic crowding compares what the individuals are. In Gentians the
    genotype is the set of clauses of the program: the genome has one bit per
    clause of the canonical clause space. The distance is the Jaccard
    distance between the two clause sets, the share of the clauses in either
    program that belong to only one of them: 0 for the same program, 1 for
    programs with no clause in common.

    Unlike the Hamming distance, which only counts the clauses that differ,
    Jaccard divides by the size of the union, so it does not depend on
    program length. Two one-clause programs with different clauses are at
    Hamming distance 2 and share nothing (Jaccard 1). Two ten-clause programs
    that share nine clauses are also at Hamming distance 2, but they are
    nearly the same program (Jaccard 2/11).

    Clauses are compared by identity. Two clauses that differ in one literal
    count as completely different. The distance says nothing about coverage:
    programs that share no clause can cover the same examples, and adding one
    clause can change the stable models of the whole program.

    Contract shared with the other replacements
    -------------------------------------------
    Fitness is maximized. The input population must be non-empty and sorted
    by descending score. A candidate with a program already in the population
    adds no genetic material and is rejected, as is a NaN or infinite score,
    which cannot be ranked. Accepted replacements return a new score-sorted
    list with the same size. Rejected candidates return the supplied
    population unchanged.
    """

    def __init__(self, crowding_factor: int) -> None:
        if (
            isinstance(crowding_factor, bool)
            or not isinstance(crowding_factor, int)
            or crowding_factor < 1
        ):
            raise ValueError("crowding factor must be an integer of at least 1")
        self.crowding_factor = crowding_factor

    def __call__(
        self,
        population: list[Individual],
        candidate: Individual,
        rng: random.Random,
    ) -> list[Individual]:
        # Not part of De Jong's algorithm, but a contract of every replacement
        # in Gentians: the population holds distinct programs with finite
        # scores.
        if (
            not population
            or any(item.genome == candidate.genome for item in population)
            or not math.isfinite(candidate.score)
        ):
            return population

        # Step 1: the crowd. `sample` draws without repetition, so a CF larger
        # than the population simply compares the candidate with everyone.
        # Drawing through the search RNG keeps runs reproducible by seed.
        crowd = rng.sample(population, min(self.crowding_factor, len(population)))

        # Step 2: the member with the most similar clauses. `min` keeps the
        # first of several equally distant members; since the crowd is in
        # random order, ties are broken at random.
        victim = min(crowd, key=lambda item: program_distance(item.genome, candidate.genome))

        # Step 3: replace only when the candidate has a higher score.
        if candidate.score <= victim.score:
            return population

        survivors = [item for item in population if item is not victim]
        survivors.append(candidate)
        return sorted(survivors, key=lambda item: item.score, reverse=True)
