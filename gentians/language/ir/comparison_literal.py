from collections.abc import Iterator
from dataclasses import dataclass, field, replace

from clingo import ast

from .. import terms as mode_terms
from ..asp import Predicate
from ..ast_nodes import comparison


@dataclass(frozen=True, slots=True)
class ComparisonLiteral:
    terms: tuple[ast.AST, ...]
    operators: tuple[str, ...]
    default_negated: bool = False
    fully_implicit_directions: bool = field(default=False, repr=False)
    double_negated: bool = False

    def __post_init__(self) -> None:
        if len(self.terms) != len(self.operators) + 1:
            raise ValueError("a comparison requires one more term than operators")
        if not self.operators:
            raise ValueError("a comparison requires at least one operator")
        if self.double_negated and not self.default_negated:
            raise ValueError("double negation requires default negation")

    @property
    def canonicalizable(self) -> bool:
        return (
            not self.default_negated
            and len(self.operators) == 1
            and self.operators[0] != "="
            and all(mode_terms.kind(term) == "variable" for term in self.terms)
        )

    @property
    def simple(self) -> bool:
        return (
            not self.default_negated
            and len(self.operators) == 1
            and all(mode_terms.kind(term) == "variable" for term in self.terms)
        )

    @property
    def arithmetic(self) -> bool:
        return any(mode_terms.contains_arithmetic(term) for term in self.terms)

    @property
    def kind(self) -> str:
        return "comparison"

    @property
    def arguments(self) -> tuple[ast.AST, ...]:
        return self.terms

    @property
    def dependencies(self) -> frozenset[Predicate]:
        return frozenset()

    def concretizations(self, constants: dict[str, tuple[ast.AST, ...]]) -> Iterator["ComparisonLiteral"]:
        if not any(mode_terms.constant_types(term) for term in self.terms):
            yield self
            return
        for concrete in mode_terms.concretize_terms(self.terms, constants):
            yield self.with_arguments(iter(concrete))

    def with_arguments(self, arguments: Iterator[ast.AST]) -> "ComparisonLiteral":
        terms = tuple(next(arguments) for _ in self.terms)
        return self if terms == self.terms else replace(self, terms=terms)

    def instantiate(self, variables: Iterator[ast.AST]) -> ast.AST:
        terms = [mode_terms.instantiate(term, variables) for term in self.terms]
        return comparison(terms, self.operators, self.default_negated, self.double_negated)
