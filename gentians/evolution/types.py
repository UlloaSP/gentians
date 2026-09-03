from dataclasses import dataclass

Behavior = tuple[int, int]


@dataclass(frozen=True, slots=True)
class FitnessResult:
    score: float
    is_solution: bool
    behavior: Behavior
