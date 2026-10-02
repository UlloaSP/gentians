from collections.abc import Iterator
from dataclasses import dataclass

from clingo import ast

from ..asp import Predicate
from ..ast_nodes import literal


@dataclass(frozen=True, slots=True)
class BooleanLiteral:
    value: bool
    default_negated: bool = False
    double_negated: bool = False

    def __post_init__(self) -> None:
        if self.double_negated and not self.default_negated:
            raise ValueError("double negation requires default negation")

    @property
    def kind(self) -> str:
        return "boolean"

    @property
    def arguments(self) -> tuple[ast.AST, ...]:
        return ()

    @property
    def dependencies(self) -> frozenset[Predicate]:
        return frozenset()

    def concretizations(self, constants: dict[str, tuple[ast.AST, ...]]) -> Iterator["BooleanLiteral"]:
        return iter((self,))

    def with_arguments(self, arguments: Iterator[ast.AST]) -> "BooleanLiteral":
        return self

    def instantiate(self, variables: Iterator[ast.AST]) -> ast.AST:
        return literal(ast.BooleanConstant(self.value), self.default_negated, self.double_negated)
