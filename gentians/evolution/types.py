from collections.abc import Callable
from typing import Protocol

from .individual import Individual

FitnessResult = tuple[float, bool] | tuple[float, bool, tuple[str, ...] | None]


class FitnessFn(Protocol):
    def __call__(self, program: tuple[str, ...]) -> FitnessResult: ...


PopulationInitializerFn = Callable[
    [int, FitnessFn],
    tuple[list[Individual], bool],
]
SelectionFn = Callable[[list[Individual]], tuple[Individual, Individual]]
CrossoverFn = Callable[
    [Individual, Individual, FitnessFn, set[tuple[str, ...]], int],
    tuple[Individual, Individual] | None,
]
MutationFn = Callable[
    [Individual, int, FitnessFn, set[tuple[str, ...]], set[tuple[str, ...]]],
    Individual,
]
ReplacementFn = Callable[
    [list[Individual], Individual, set[tuple[str, ...]]],
    list[Individual],
]
