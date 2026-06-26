from collections.abc import Callable
from typing import Protocol

from .individual import Individual


class FitnessFn(Protocol):
    def __call__(self, program: list[str]) -> tuple[float, bool, list[int]]: ...


PopulationInitializerFn = Callable[
    [int, list[str], FitnessFn],
    tuple[list[Individual], bool],
]
SelectionFn = Callable[[list[Individual]], tuple[Individual, Individual]]
CrossoverFn = Callable[
    [Individual, Individual, FitnessFn, set[tuple[str, ...]]],
    tuple[Individual, Individual],
]
MutationFn = Callable[
    [Individual, list[str], FitnessFn, set[tuple[str, ...]]],
    Individual,
]
ReplacementFn = Callable[
    [list[Individual], Individual],
    list[Individual],
]
