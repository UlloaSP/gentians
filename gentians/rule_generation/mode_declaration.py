from dataclasses import dataclass

from .atom_literal import AtomLiteral


@dataclass(frozen=True, slots=True)
class ModeDeclaration:
    recall: int
    literal: AtomLiteral

    def __post_init__(self) -> None:
        if self.recall != -1 and self.recall < 1:
            raise ValueError("mode recall must be positive or unbounded")
        if self.literal.default_negated and any(
            binding.direction == "output" for binding in self.literal.atom.bindings()
        ):
            raise ValueError("default-negated modes cannot produce output variables")
