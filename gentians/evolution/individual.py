from dataclasses import dataclass, field
import time


@dataclass(slots=True)
class Individual:
    program: list[str]
    score: float
    is_best: bool  # does this cover everything positive and no negative?
    generated_timestamp: float = field(default_factory=time.time)
    signature: tuple[str, ...] = field(init=False)

    def __post_init__(self) -> None:
        self.signature = tuple(self.program)

    def __str__(self) -> str:
        return f"Program: {self.program} - score: {self.score}"

    def __repr__(self) -> str:
        return self.__str__()
