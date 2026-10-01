from collections.abc import Iterator
from dataclasses import dataclass
from itertools import product

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
        term_choices = tuple(tuple(mode_terms.concretizations(term, constants)) for term in self.terms)
        conclusions = tuple(self.conclusion.concretizations(constants)) if self.conclusion is not None else (None,)
        condition_choices = tuple(tuple(condition.concretizations(constants)) for condition in self.conditions)
        for concrete_terms in product(*term_choices):
            for conclusion in conclusions:
                for conditions in product(*condition_choices):
                    yield (
                        self if concrete_terms == self.terms and conditions == self.conditions
                        and conclusion == self.conclusion
                        else AggregateElement(concrete_terms, conditions, conclusion)
                    )

    def instantiate(self, variables: Iterator[ast.AST]) -> ast.AST:
        terms = [mode_terms.instantiate(term, variables) for term in self.terms]
        conclusion = self.conclusion.instantiate(variables) if self.conclusion is not None else None
        conditions = [condition.instantiate(variables) for condition in self.conditions]
        if conclusion is not None:
            return ast.ConditionalLiteral(LOCATION, conclusion, conditions)
        return ast.BodyAggregateElement(terms, conditions)
