from collections.abc import Iterator
from dataclasses import dataclass

from clingo import ast

from .. import terms as mode_terms
from ..ast_nodes import LOCATION
from .atom_literal import AtomLiteral
from .boolean_literal import BooleanLiteral
from .comparison_literal import ComparisonLiteral


@dataclass(frozen=True, slots=True)
class AggregateElement:
    terms: tuple[ast.AST, ...]
    conditions: tuple[AtomLiteral | BooleanLiteral | ComparisonLiteral, ...]
    conclusion: AtomLiteral | BooleanLiteral | ComparisonLiteral | None = None

    def __post_init__(self) -> None:
        if self.conclusion is not None and self.terms:
            raise ValueError("aggregate element needs a tuple or a set atom")

    @property
    def arguments(self) -> tuple[ast.AST, ...]:
        return (
            *self.terms,
            *(self.conclusion.arguments if self.conclusion is not None else ()),
            *(term for condition in self.conditions for term in condition.arguments),
        )

    def concretizations(
        self, constants: dict[str, tuple[ast.AST, ...]]
    ) -> Iterator["AggregateElement"]:
        if not any(mode_terms.constant_types(term) for term in self.arguments):
            yield self
            return
        for concrete in mode_terms.concretize_terms(self.arguments, constants):
            yield self.with_arguments(iter(concrete))

    def with_arguments(self, arguments: Iterator[ast.AST]) -> "AggregateElement":
        terms = tuple(next(arguments) for _ in self.terms)
        conclusion = self.conclusion.with_arguments(arguments) if self.conclusion is not None else None
        conditions = tuple(condition.with_arguments(arguments) for condition in self.conditions)
        return (
            self if terms == self.terms and conclusion == self.conclusion and conditions == self.conditions
            else AggregateElement(terms, conditions, conclusion)
        )

    def instantiate(self, variables: Iterator[ast.AST]) -> ast.AST:
        terms = [mode_terms.instantiate(term, variables) for term in self.terms]
        conclusion = self.conclusion.instantiate(variables) if self.conclusion is not None else None
        conditions = [condition.instantiate(variables) for condition in self.conditions]
        if conclusion is not None:
            return ast.ConditionalLiteral(LOCATION, conclusion, conditions)
        return ast.BodyAggregateElement(terms, conditions)
