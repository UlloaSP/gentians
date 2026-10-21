from dataclasses import dataclass

Behavior = tuple[int, int]


def dominates(first: Behavior, second: Behavior) -> bool:
    """Whether `first` covers every positive and no negative beyond `second`."""
    return not (second[0] & ~first[0] or first[1] & ~second[1])


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    score: float
    is_solution: bool
    behavior: Behavior
    is_complete: bool
    is_consistent: bool
