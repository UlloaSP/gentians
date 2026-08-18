import re
from dataclasses import dataclass

from .mode_argument import ModeArgument


@dataclass(frozen=True, slots=True)
class ModeDeclaration:
    """Normal predicate template, recall, polarity, and section."""

    recall: int
    name: str
    arguments: tuple[ModeArgument, ...]
    positive: bool
    head: bool

    def __post_init__(self) -> None:
        if self.recall != -1 and self.recall < 1:
            raise ValueError("mode recall must be positive or unbounded")
        if not re.fullmatch(r"[a-z][A-Za-z0-9_]*", self.name):
            raise ValueError(f"invalid mode predicate: {self.name}")
        if self.head and not self.positive:
            raise ValueError("head modes must be positive")
        if not self.positive and any(
            argument.direction == "output" for argument in self.arguments
        ):
            raise ValueError("negative body modes cannot produce output variables")

    @property
    def arity(self) -> int:
        return len(self.arguments)
