from collections.abc import Iterator
from dataclasses import dataclass
from itertools import product

from clingo import ast

from .. import terms as mode_terms
from ..asp import Predicate
from ..ast_nodes import LOCATION
from .atom_literal import AtomLiteral
from .boolean_literal import BooleanLiteral
from .comparison_literal import ComparisonLiteral


@dataclass(frozen=True, slots=True)
class ConditionalLiteral:
    conclusion: AtomLiteral | BooleanLiteral | ComparisonLiteral
    conditions: tuple[AtomLiteral | BooleanLiteral | ComparisonLiteral, ...]
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
            for binding in mode_terms.bindings(term)
        ):
            raise ValueError("conditional conditions cannot produce output variables")
        if isinstance(self.conclusion, ComparisonLiteral) and any(
            binding.direction == "output"
            for term in self.conclusion.arguments
            for binding in mode_terms.bindings(term)
        ):
            raise ValueError("conditional comparisons cannot produce output variables")

    @property
    def kind(self) -> str:
        return "conditional"

    @property
    def arguments(self) -> tuple[ast.AST, ...]:
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
        self, constants: dict[str, tuple[ast.AST, ...]]
    ) -> tuple["ConditionalLiteral", ...]:
        return tuple(
            ConditionalLiteral(conclusion, conditions, self.condition_groups)
            for conclusion, conditions in product(
                self.conclusion.concretizations(constants),
                product(*(item.concretizations(constants) for item in self.conditions)),
            )
        )

    def instantiate(self, variables: Iterator[str]) -> ast.AST:
        conclusion = self.conclusion.instantiate(variables)
        conditions = [condition.instantiate(variables) for condition in self.conditions]
        return ast.ConditionalLiteral(LOCATION, conclusion, conditions)
