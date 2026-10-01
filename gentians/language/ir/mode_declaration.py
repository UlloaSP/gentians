from dataclasses import dataclass

from .. import terms as mode_terms
from .aggregate_literal import AggregateLiteral
from .atom_literal import AtomLiteral
from .boolean_literal import BooleanLiteral
from .comparison_literal import ComparisonLiteral
from .conditional_literal import ConditionalLiteral
from .literal_template import anonymous_is_safe


@dataclass(frozen=True, slots=True)
class ModeDeclaration:
    recall: int
    literal: (
        AggregateLiteral
        | AtomLiteral
        | BooleanLiteral
        | ComparisonLiteral
        | ConditionalLiteral
    )

    def __post_init__(self) -> None:
        if self.recall != -1 and self.recall < 1:
            raise ValueError("mode recall must be positive or unbounded")
        if not anonymous_is_safe(self.literal):
            raise ValueError("anonymous variables need a positive body atom")
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
        mode_terms.validate_labels(self.literal.arguments, "mode")
