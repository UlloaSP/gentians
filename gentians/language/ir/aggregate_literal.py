from collections.abc import Iterator
from dataclasses import dataclass

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
        left = self.left_guard
        return left if (
            left is not None
            and left.comparison == ast.ComparisonOperator.Equal
            and self.right_guard is None
            and mode_terms.kind(left.term) == "variable"
            and mode_terms.binding(left.term).direction == "output"
        ) else None

    def concretizations(
        self, constants: dict[str, tuple[ast.AST, ...]]
    ) -> Iterator["AggregateLiteral"]:
        if not any(mode_terms.constant_types(term) for term in self.arguments):
            yield self
            return
        for concrete in mode_terms.concretize_terms(self.arguments, constants):
            arguments = iter(concrete)
            elements = tuple(element.with_arguments(arguments) for element in self.elements)
            left = mode_terms.replace_guard_term(self.left_guard, arguments)
            right = mode_terms.replace_guard_term(self.right_guard, arguments)
            yield (
                self if elements == self.elements and left == self.left_guard
                and right == self.right_guard else AggregateLiteral(
                    self.function, elements, left, right,
                    self.default_negated, self.double_negated,
                )
            )

    def instantiate(self, variables: Iterator[ast.AST]) -> ast.AST:
        # The generator numbers element bindings before guard bindings.
        elements = [element.instantiate(variables) for element in self.elements]
        left = mode_terms.instantiate_guard(self.left_guard, variables)
        right = mode_terms.instantiate_guard(self.right_guard, variables)
        aggregate = (
            ast.Aggregate(LOCATION, left, elements, right) if self.function == "set" else
            ast.BodyAggregate(LOCATION, left, AGGREGATE_FUNCTIONS[self.function], elements, right)
        )
        return literal(aggregate, self.default_negated, self.double_negated)
