from collections.abc import Iterator
from dataclasses import dataclass
from itertools import product

from clingo import ast

from .. import terms as mode_terms
from ..asp import Predicate
from ..ast_nodes import AGGREGATE_FUNCTIONS, LOCATION, literal
from .aggregate_element import AggregateElement
from .atom_literal import AtomLiteral


@dataclass(frozen=True, slots=True)
class AggregateLiteral:
    function: str
    elements: tuple[AggregateElement, ...]
    left_guard: ast.AST | None
    right_guard: ast.AST | None = None
    default_negated: bool = False
    double_negated: bool = False

    def __post_init__(self) -> None:
        if self.double_negated and not self.default_negated:
            raise ValueError("double negation requires default negation")

    @property
    def kind(self) -> str:
        return "aggregate"

    @property
    def arguments(self) -> tuple[ast.AST, ...]:
        return (
            *(term for element in self.elements for term in element.arguments),
            *((self.left_guard.term,) if self.left_guard else ()),
            *((self.right_guard.term,) if self.right_guard else ()),
        )

    @property
    def dependencies(self) -> frozenset[Predicate]:
        return frozenset(
            dependency
            for element in self.elements
            for dependency in (
                *((element.conclusion.atom.signature,)
                  if isinstance(element.conclusion, AtomLiteral) else ()),
                *(item for condition in element.conditions for item in condition.dependencies),
            )
        )

    @property
    def output_guard(self) -> ast.AST | None:
        if (
            self.left_guard is not None
            and self.left_guard.comparison == ast.ComparisonOperator.Equal
            and self.right_guard is None
            and mode_terms.kind(self.left_guard.term) == "variable"
            and mode_terms.binding(self.left_guard.term).direction == "output"
        ):
            return self.left_guard
        return None

    def concretizations(
        self, constants: dict[str, tuple[str, ...]]
    ) -> tuple["AggregateLiteral", ...]:
        return tuple(
            AggregateLiteral(
                self.function, elements, left, right,
                self.default_negated, self.double_negated,
            )
            for elements in product(
                *(element.concretizations(constants) for element in self.elements)
            )
            for left in (
                tuple(self.left_guard.update(term=term) for term in mode_terms.concretizations(self.left_guard.term, constants))
                if self.left_guard is not None else (None,)
            )
            for right in (
                tuple(self.right_guard.update(term=term) for term in mode_terms.concretizations(self.right_guard.term, constants))
                if self.right_guard is not None else (None,)
            )
        )

    def instantiate(self, variables: Iterator[str]) -> ast.AST:
        # The generator numbers element bindings before guard bindings.
        elements = [element.instantiate(variables) for element in self.elements]
        left = self.left_guard.update(term=mode_terms.instantiate(self.left_guard.term, variables)) if self.left_guard else None
        right = self.right_guard.update(term=mode_terms.instantiate(self.right_guard.term, variables)) if self.right_guard else None
        aggregate = (
            ast.Aggregate(LOCATION, left, elements, right) if self.function == "set" else
            ast.BodyAggregate(LOCATION, left, AGGREGATE_FUNCTIONS[self.function], elements, right)
        )
        return literal(aggregate, self.default_negated, self.double_negated)
