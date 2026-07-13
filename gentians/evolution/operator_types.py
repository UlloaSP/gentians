from collections.abc import Callable
import random

from .evolution_context import EvolutionContext
from .individual import Individual
from .types import Genome


PopulationInitializerFn = Callable[[EvolutionContext], list[Genome]]
SelectionFn = Callable[
    [list[Individual], random.Random], tuple[Individual, Individual]
]
CrossoverFn = Callable[[Genome, Genome, EvolutionContext], tuple[Genome, ...]]
MutationFn = Callable[[Genome, EvolutionContext], Genome]
ReplacementFn = Callable[
    [list[Individual], Individual, random.Random], list[Individual]
]
