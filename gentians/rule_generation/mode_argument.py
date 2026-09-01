import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModeArgument:
    """Typed variable or constant placeholder in a normal mode."""

    kind: str
    type: str
    direction: str = ""
    label: str = ""

    def __post_init__(self) -> None:
        if self.type == "any" or not re.fullmatch(r"[a-z][A-Za-z0-9_]*", self.type):
            raise ValueError(f"invalid mode argument type: {self.type}")
        if self.kind == "variable":
            if self.direction not in {"input", "output", "any"}:
                raise ValueError("variables require input, output, or any direction")
            if self.label and not re.fullmatch(r"[a-z][A-Za-z0-9_]*", self.label):
                raise ValueError(f"invalid variable label: {self.label}")
        elif self.kind == "constant":
            if self.direction or self.label:
                raise ValueError("constant placeholders cannot have direction or label")
        else:
            raise ValueError(f"invalid mode argument kind: {self.kind}")
