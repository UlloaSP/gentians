from collections.abc import Iterator
from dataclasses import dataclass, field

from clingo import ast

from .. import terms as mode_terms
from ..asp import Predicate
from ..ast_nodes import LOCATION
from .atom_literal import AtomLiteral
from .boolean_literal import BooleanLiteral
from .comparison_literal import ComparisonLiteral


@dataclass(frozen=True, slots=True)
class HeadAggregateElement:
    terms: tuple[ast.AST, ...]
    conclusion: AtomLiteral | BooleanLiteral | ComparisonLiteral
    conditions: tuple[AtomLiteral | BooleanLiteral | ComparisonLiteral, ...]
    arguments: tuple[ast.AST, ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if any(
            binding.direction == "output"
            for condition in self.conditions
            for term in condition.arguments
            for binding in mode_terms.bindings(term)
        ):
            raise ValueError("aggregate head conditions cannot produce outputs")
        object.__setattr__(self, "arguments", (
            *self.terms,
            *self.conclusion.arguments,
            *(term for condition in self.conditions for term in condition.arguments),
        ))

    @property
    def kind(self) -> str:
        return "head_aggregate"

    @property
    def dependencies(self) -> frozenset[Predicate]:
        dependencies = {
            predicate for item in self.conditions for predicate in item.dependencies
        }
        if (
            not isinstance(self.conclusion, AtomLiteral)
            or self.conclusion.default_negated
        ):
            dependencies.update(self.conclusion.dependencies)
        return frozenset(dependencies)

    def concretizations(
        self, constants: dict[str, tuple[ast.AST, ...]]
    ) -> Iterator["HeadAggregateElement"]:
        if not any(mode_terms.constant_types(term) for term in self.arguments):
            yield self
            return
        for concrete in mode_terms.concretize_terms(self.arguments, constants):
            yield self.with_arguments(iter(concrete))

    def with_arguments(self, arguments: Iterator[ast.AST]) -> "HeadAggregateElement":
        terms = tuple(next(arguments) for _ in self.terms)
        conclusion = self.conclusion.with_arguments(arguments)
        conditions = tuple(condition.with_arguments(arguments) for condition in self.conditions)
        return (
            self if terms == self.terms and conclusion == self.conclusion and conditions == self.conditions
            else HeadAggregateElement(terms, conclusion, conditions)
        )

    def instantiate(self, variables: Iterator[ast.AST]) -> ast.AST:
        terms = [mode_terms.instantiate(term, variables) for term in self.terms]
        conclusion = self.conclusion.instantiate(variables)
        conditions = [condition.instantiate(variables) for condition in self.conditions]
        return ast.HeadAggregateElement(
            terms, ast.ConditionalLiteral(LOCATION, conclusion, conditions)
        )
