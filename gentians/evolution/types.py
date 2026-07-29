from dataclasses import dataclass


Genome = int
ProgramText = tuple[str, ...]
Behavior = tuple[int, int]


@dataclass(frozen=True, slots=True)
class FitnessResult:
    score: float
    is_best: bool
    best_program: ProgramText | None
    behavior: Behavior
