from dataclasses import dataclass, field
import time


@dataclass(slots=True)
class Individual:
    program: tuple[str, ...]
    score: float
    is_best: bool  # does this cover everything positive and no negative?
    generated_timestamp: float = field(default_factory=time.time)

    def __str__(self) -> str:
        return f"Program: {self.program} - score: {self.score}"

    def __repr__(self) -> str:
        return self.__str__()
