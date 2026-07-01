from collections.abc import Callable
from typing import Protocol

from .individual import Individual
from ..rule_generation.rule_space import RuleSpace


class FitnessFn(Protocol):
    def __call__(self, program: list[str]) -> tuple[float, bool, list[int]]: ...


PopulationInitializerFn = Callable[
    [int, RuleSpace, FitnessFn],
    tuple[list[Individual], bool],
]
SelectionFn = Callable[[list[Individual]], tuple[Individual, Individual]]
CrossoverFn = Callable[
    [Individual, Individual, FitnessFn, set[tuple[str, ...]], int],
    tuple[Individual, Individual],
]
MutationFn = Callable[
    [Individual, RuleSpace, int, FitnessFn, set[tuple[str, ...]]],
    Individual,
]
ReplacementFn = Callable[
    [list[Individual], Individual, set[tuple[str, ...]]],
    list[Individual],
]
