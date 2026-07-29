import random
from collections.abc import Callable
from dataclasses import dataclass

from .evolution_context import EvolutionContext
from .individual import Individual
from .types import Genome


@dataclass(frozen=True, slots=True)
class MutationProposal:
    program: Genome
    operation: str | None = None
    local: bool | None = None
    skipped: bool = False


PopulationInitializerFn = Callable[[EvolutionContext], list[Genome]]
SelectionFn = Callable[[list[Individual], random.Random], tuple[Individual, Individual]]
CrossoverFn = Callable[[Genome, Genome, EvolutionContext], tuple[Genome, ...]]
MutationFn = Callable[[Genome, EvolutionContext], MutationProposal]
ReplacementFn = Callable[
    [list[Individual], Individual, random.Random], list[Individual]
]
