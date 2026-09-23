from dataclasses import dataclass

from .aggregate_literal import AggregateLiteral
from .atom_literal import AtomLiteral
from .boolean_literal import BooleanLiteral
from .comparison_literal import ComparisonLiteral
from .conditional_literal import ConditionalLiteral


@dataclass(frozen=True, slots=True)
class ModeDeclaration:
    recall: int
    literal: AggregateLiteral | AtomLiteral | BooleanLiteral | ComparisonLiteral | ConditionalLiteral

    def __post_init__(self) -> None:
        if self.recall != -1 and self.recall < 1:
            raise ValueError("mode recall must be positive or unbounded")
        if isinstance(self.literal, AtomLiteral):
            anonymous_is_safe = (
                not self.literal.default_negated
                or not any(term.contains_anonymous for term in self.literal.arguments)
            )
        elif isinstance(self.literal, ConditionalLiteral):
            anonymous_is_safe = not any(
                term.contains_anonymous for term in self.literal.conclusion.arguments
            ) and all(
                not any(term.contains_anonymous for term in condition.arguments)
                or isinstance(condition, AtomLiteral) and not condition.default_negated
                for condition in self.literal.conditions
            )
        elif isinstance(self.literal, AggregateLiteral):
            anonymous_is_safe = all(
                not any(term.contains_anonymous for term in element.terms)
                and (element.conclusion is None or not any(
                    term.contains_anonymous for term in element.conclusion.arguments
                ))
                and all(
                    not any(term.contains_anonymous for term in condition.arguments)
                    or isinstance(condition, AtomLiteral) and not condition.default_negated
                    for condition in element.conditions
                )
                for element in self.literal.elements
            ) and all(
                guard is None or not guard.term.contains_anonymous
                for guard in (self.literal.left_guard, self.literal.right_guard)
            )
        else:
            anonymous_is_safe = not any(
                term.contains_anonymous for term in self.literal.arguments
            )
        if not anonymous_is_safe:
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
