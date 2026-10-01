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
    ) -> tuple["AggregateElement", ...]:
        return tuple(
            AggregateElement(concrete_terms, conditions, conclusion)
            for concrete_terms, conclusion, conditions in product(
                product(*(mode_terms.concretizations(term, constants) for term in self.terms)),
                self.conclusion.concretizations(constants) if self.conclusion is not None else (None,),
                product(*(condition.concretizations(constants) for condition in self.conditions)),
            )
        )

    def instantiate(self, variables: Iterator[str]) -> ast.AST:
        terms = [mode_terms.instantiate(term, variables) for term in self.terms]
        conclusion = self.conclusion.instantiate(variables) if self.conclusion is not None else None
        conditions = [condition.instantiate(variables) for condition in self.conditions]
        if conclusion is not None:
            return ast.ConditionalLiteral(LOCATION, conclusion, conditions)
        return ast.BodyAggregateElement(terms, conditions)
