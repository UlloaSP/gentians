import random
from collections.abc import Callable
from dataclasses import dataclass

from .context import EvolutionContext
from .individual import Individual
from ..hypotheses import Genome


@dataclass(frozen=True, slots=True)
class MutationProposal:
    genome: Genome
    operation: str | None = None
    local: bool | None = None
    skipped: bool = False


PopulationInitializerFn = Callable[[EvolutionContext], list[Genome]]
# The algorithm supplies the parent count. A strategy decides whether draws use
# replacement; lexicase keeps parents distinct within one mating event.
SelectionFn = Callable[[list[Individual], int, random.Random], list[Individual]]
CrossoverFn = Callable[[Genome, Genome, EvolutionContext], Genome | None]
MutationFn = Callable[[Genome, EvolutionContext, bool], MutationProposal]
ReplacementFn = Callable[
    [list[Individual], Individual, random.Random], list[Individual]
]

# Called once per generation with the champion found so far. Returns the
# survivors that seed a restarted population, or None. The final flag is False
# while the algorithm forbids restarting, so the strategy can still observe
# progress. The algorithm rebuilds the population and owns its caches.
RestartFn = Callable[
    [int, list[Individual], Individual, EvolutionContext, bool],
    list[Individual] | None,
]
