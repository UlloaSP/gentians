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
class HeadAggregateElement:
    terms: tuple[ast.AST, ...]
    conclusion: AtomLiteral | BooleanLiteral | ComparisonLiteral
    conditions: tuple[AtomLiteral | BooleanLiteral | ComparisonLiteral, ...]

    def __post_init__(self) -> None:
        if any(
            binding.direction == "output"
            for condition in self.conditions
            for term in condition.arguments
            for binding in mode_terms.bindings(term)
        ):
            raise ValueError("aggregate head conditions cannot produce outputs")

    @property
    def kind(self) -> str:
        return "head_aggregate"

    @property
    def arguments(self) -> tuple[ast.AST, ...]:
        return (
            *self.terms,
            *self.conclusion.arguments,
            *(term for condition in self.conditions for term in condition.arguments),
        )

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
        term_choices = tuple(tuple(mode_terms.concretizations(term, constants)) for term in self.terms)
        conclusions = tuple(self.conclusion.concretizations(constants))
        condition_choices = tuple(tuple(condition.concretizations(constants)) for condition in self.conditions)
        for terms in product(*term_choices):
            for conclusion in conclusions:
                for conditions in product(*condition_choices):
                    yield (
                        self if terms == self.terms and conclusion == self.conclusion
                        and conditions == self.conditions
                        else HeadAggregateElement(terms, conclusion, conditions)
                    )

    def instantiate(self, variables: Iterator[ast.AST]) -> ast.AST:
        terms = [mode_terms.instantiate(term, variables) for term in self.terms]
        conclusion = self.conclusion.instantiate(variables)
        conditions = [condition.instantiate(variables) for condition in self.conditions]
        return ast.HeadAggregateElement(
            terms, ast.ConditionalLiteral(LOCATION, conclusion, conditions)
        )
