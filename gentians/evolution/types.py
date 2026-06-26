from collections.abc import Callable
from typing import Protocol

from .individual import Individual
from ..rule_generation.placed_clause import PlacedClause


class FitnessFn(Protocol):
    def __call__(
        self, stub_indexes: list[int], prog_indexes: list[int], program: list[str]
    ) -> tuple[float, bool, list[int]]: ...


PopulationInitializerFn = Callable[
    [int, list[PlacedClause], FitnessFn],
    tuple[list[Individual], bool],
]
SelectionFn = Callable[[list[Individual]], tuple[Individual, Individual]]
CrossoverFn = Callable[
    [Individual, Individual, FitnessFn], tuple[Individual, Individual]
]
MutationFn = Callable[
    [Individual, list[PlacedClause], FitnessFn],
    Individual,
]
ReplacementFn = Callable[
    [list[Individual], Individual],
    list[Individual],
]
