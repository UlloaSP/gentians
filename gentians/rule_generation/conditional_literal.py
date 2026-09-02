from collections.abc import Iterator
from dataclasses import dataclass

from .atom_literal import AtomLiteral
from .comparison_literal import ComparisonLiteral
from .parser import Predicate
from .term_template import TermTemplate


@dataclass(frozen=True, slots=True)
class ConditionalLiteral:
    conclusion: AtomLiteral
    conditions: tuple[AtomLiteral | ComparisonLiteral, ...]
    condition_groups: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.conditions:
            raise ValueError("conditional literals require at least one condition")
        if len(self.conditions) != len(self.condition_groups):
            raise ValueError(
                "every conditional literal condition requires a recall group"
            )
        if any(
            binding.direction == "output"
            for condition in self.conditions
            for term in condition.arguments
            for binding in term.bindings()
        ):
            raise ValueError("conditional conditions cannot produce output variables")

    @property
    def kind(self) -> str:
        return "conditional"

    @property
    def arguments(self) -> tuple[TermTemplate, ...]:
        return (
            *self.conclusion.arguments,
            *(term for condition in self.conditions for term in condition.arguments),
        )

    @property
    def dependencies(self) -> frozenset[Predicate]:
        return frozenset(
            predicate
            for literal in (self.conclusion, *self.conditions)
            for predicate in literal.dependencies
        )

    def concretizations(
        self, constants: dict[str, tuple[str, ...]]
    ) -> tuple["ConditionalLiteral", ...]:
        from itertools import product

        def concrete(
            literal: AtomLiteral | ComparisonLiteral,
        ) -> tuple[AtomLiteral | ComparisonLiteral, ...]:
            if isinstance(literal, AtomLiteral):
                return tuple(
                    AtomLiteral(atom, literal.default_negated)
                    for atom in literal.atom.concretizations(constants)
                )
            return tuple(
                ComparisonLiteral(
                    literal.operator, (terms[0], terms[1]), literal.family
                )
                for terms in product(
                    *(term.concretizations(constants) for term in literal.terms)
                )
            )

        return tuple(
            ConditionalLiteral(conclusion, conditions, self.condition_groups)
            for conclusion in concrete(self.conclusion)
            if isinstance(conclusion, AtomLiteral)
            for conditions in product(*(concrete(item) for item in self.conditions))
        )

    def render(self, variables: Iterator[str]) -> str:
        conclusion = self.conclusion.render(variables)
        conditions = ",".join(
            condition.render(variables) for condition in self.conditions
        )
        return f"{conclusion}:{conditions}"
