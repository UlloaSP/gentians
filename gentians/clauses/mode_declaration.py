from dataclasses import dataclass

from .atom_literal import AtomLiteral
from .comparison_literal import ComparisonLiteral
from .conditional_literal import ConditionalLiteral


@dataclass(frozen=True, slots=True)
class ModeDeclaration:
    recall: int
    literal: AtomLiteral | ComparisonLiteral | ConditionalLiteral

    def __post_init__(self) -> None:
        if self.recall != -1 and self.recall < 1:
            raise ValueError("mode recall must be positive or unbounded")
        conclusion = (
            self.literal.conclusion
            if isinstance(self.literal, ConditionalLiteral)
            else self.literal
        )
        if (
            isinstance(conclusion, AtomLiteral)
            and conclusion.default_negated
            and any(
                binding.direction == "output" for binding in conclusion.atom.bindings()
            )
        ):
            raise ValueError("default-negated modes cannot produce output variables")
        labels: dict[str, str] = {}
        for term in self.literal.arguments:
            for binding in term.bindings():
                if not binding.label:
                    continue
                previous = labels.setdefault(binding.label, binding.type)
                if previous != binding.type:
                    raise ValueError(
                        f"mode variable label {binding.label} has incompatible types"
                    )
