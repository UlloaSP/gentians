from collections import Counter

from ..context import EvolutionContext
from ...hypotheses import Genome
from .random_population import RandomPopulation


class StructuralDiversePopulation:
    """Select distinct closed programs by size balance, then Jaccard distance."""

    def __init__(self, size: int) -> None:
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            raise ValueError("population size must be a positive integer")
        self.size = size

    def __call__(self, context: EvolutionContext) -> list[Genome]:
        # ponytail: bounded 4x structural sampling, no candidate fitness queries.
        # Closure may change size, so rank actual genomes rather than seed sizes.
        candidates = RandomPopulation(4 * self.size)(context)
        selected: list[Genome] = []
        sizes: Counter[int] = Counter()
        while candidates and len(selected) < self.size:
            candidate = max(candidates, key=lambda genome: (
                -sizes[genome.bit_count()],
                min(((genome ^ other).bit_count() / (genome | other).bit_count()
                     for other in selected), default=0.0),
            ))
            selected.append(candidate)
            sizes[candidate.bit_count()] += 1
            candidates.remove(candidate)
        return selected
