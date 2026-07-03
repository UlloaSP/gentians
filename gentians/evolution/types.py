from collections.abc import Callable
from typing import Protocol

from .individual import Individual


class FitnessFn(Protocol):
    def __call__(self, program: tuple[str, ...]) -> tuple[float, bool]: ...


PopulationInitializerFn = Callable[
    [int, FitnessFn],
    tuple[list[Individual], bool],
]
SelectionFn = Callable[[list[Individual]], tuple[Individual, Individual]]
CrossoverFn = Callable[
    [Individual, Individual, FitnessFn, set[tuple[str, ...]], int],
    tuple[Individual, Individual],
]
MutationFn = Callable[
    [Individual, int, FitnessFn, set[tuple[str, ...]], set[tuple[str, ...]]],
    Individual,
]
ReplacementFn = Callable[
    [list[Individual], Individual, set[tuple[str, ...]]],
    list[Individual],
]
