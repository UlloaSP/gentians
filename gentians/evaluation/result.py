from dataclasses import dataclass

Behavior = tuple[int, int]


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    score: float
    is_solution: bool
    behavior: Behavior
    is_complete: bool
    is_consistent: bool
    # Coverage ceiling with learned integrity constraints removed. None means
    # unmeasured; this is not a score or a claim about individual clauses.
    potential_pos_mask: int | None = None
    potential_complete: bool | None = None
