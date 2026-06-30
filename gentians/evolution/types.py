from collections.abc import Callable
from typing import Protocol

from .individual import Individual
from ..rule_generation.rule_space import RuleId, RuleSpace


class FitnessFn(Protocol):
    def __call__(self, program: list[RuleId]) -> tuple[float, bool, list[int]]: ...


PopulationInitializerFn = Callable[
    [int, RuleSpace, FitnessFn],
    tuple[list[Individual], bool],
]
SelectionFn = Callable[[list[Individual]], tuple[Individual, Individual]]
CrossoverFn = Callable[
    [Individual, Individual, FitnessFn, set[tuple[RuleId, ...]], int],
    tuple[Individual, Individual],
]
MutationFn = Callable[
    [Individual, RuleSpace, int, FitnessFn, set[tuple[RuleId, ...]]],
    Individual,
]
ReplacementFn = Callable[
    [list[Individual], Individual, set[tuple[RuleId, ...]]],
    list[Individual],
]
