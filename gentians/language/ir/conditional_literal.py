from collections.abc import Iterator
from dataclasses import dataclass

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
    ) -> Iterator["ConditionalLiteral"]:
        if not any(mode_terms.constant_types(term) for term in self.arguments):
            yield self
            return
        for concrete in mode_terms.concretize_terms(self.arguments, constants):
            yield self.with_arguments(iter(concrete))

    def with_arguments(self, arguments: Iterator[ast.AST]) -> "ConditionalLiteral":
        conclusion = self.conclusion.with_arguments(arguments)
        conditions = tuple(condition.with_arguments(arguments) for condition in self.conditions)
        return (
            self if conclusion == self.conclusion and conditions == self.conditions
            else ConditionalLiteral(conclusion, conditions, self.condition_groups)
        )

    def instantiate(self, variables: Iterator[ast.AST]) -> ast.AST:
        conclusion = self.conclusion.instantiate(variables)
        conditions = [condition.instantiate(variables) for condition in self.conditions]
        return ast.ConditionalLiteral(LOCATION, conclusion, conditions)
