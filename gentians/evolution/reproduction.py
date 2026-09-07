from collections.abc import Iterable
from dataclasses import dataclass, field

from ..hypotheses import Genome
from .individual import Individual


@dataclass(slots=True)
class ReproductiveHistory:
    """Observed improvement rates for complete parent programs, not their clauses."""

    _counts: dict[Genome, tuple[float, float]] = field(default_factory=dict)

    def observe(
        self,
        first: Individual,
        second: Individual,
        child: Individual | None,
        duplicate: bool = False,
    ) -> None:
        reward = float(
            not duplicate
            and child is not None
            and child.score > max(first.score, second.score)
        )
        for genome in dict.fromkeys((first.genome, second.genome)):
            attempts, successes = self._counts.get(genome, (0.0, 0.0))
            self._counts[genome] = attempts + 1.0, successes + reward

    def value(self, genome: Genome) -> float:
        attempts, successes = self._counts.get(genome, (0.0, 0.0))
        return (successes + 1.0) / (attempts + 2.0)

    def attempts(self, genome: Genome) -> float:
        return self._counts.get(genome, (0.0, 0.0))[0]

    def retain(self, genomes: Iterable[Genome]) -> None:
        """Forget parents that can no longer be selected from the population."""
        retained = set(genomes)
        self._counts = {
            genome: counts
            for genome, counts in self._counts.items()
            if genome in retained
        }

    def decay(self, factor: float = 0.5) -> None:
        """Reduce evidence weight when the available reproductive context changes."""
        if not 0 <= factor <= 1:
            raise ValueError("reproductive decay must be between 0 and 1")
        self._counts = {
            genome: (attempts * factor, successes * factor)
            for genome, (attempts, successes) in self._counts.items()
        }

    def remap(self, genomes: dict[Genome, Genome]) -> None:
        """Preserve retained parents' credit when a sampled pool replaces its indices."""
        self._counts = {genomes[genome]: counts for genome, counts in self._counts.items()
                        if genome in genomes}
