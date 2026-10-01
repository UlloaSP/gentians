from collections.abc import Iterator
from dataclasses import dataclass, field

from clingo import ast

from .. import terms as mode_terms
from ..asp import Predicate
from ..ast_nodes import comparison


@dataclass(frozen=True, slots=True)
class ArithmeticLiteral:
    expression: ast.AST
    output: ast.AST
    complexity: int = 1
    implicit_additive_family_member: bool = field(
        default=False, repr=False
    )

    def __post_init__(self) -> None:
        if mode_terms.kind(self.expression) != "arithmetic" or len(self.arguments) != 3:
            raise ValueError(
                "arithmetic literals require a binary arithmetic expression"
            )

    @property
    def kind(self) -> str:
        return "arithmetic"

    @property
    def arguments(self) -> tuple[ast.AST, ...]:
        expression = self.expression.argument if self.operator == "abs" else self.expression
        return (*mode_terms.arguments(expression), self.output)

    @property
    def operator(self) -> str:
        if (
            self.expression.ast_type == ast.ASTType.UnaryOperation
            and self.expression.operator_type == ast.UnaryOperator.Absolute
            and self.expression.argument.ast_type == ast.ASTType.BinaryOperation
            and self.expression.argument.operator_type == ast.BinaryOperator.Minus
        ):
            return "abs"
        return mode_terms.value(self.expression)

    @property
    def coefficients(self) -> tuple[int, ...] | None:
        coefficients = _linear_coefficients(self.expression, 1)
        if coefficients is None:
            return None
        return (*coefficients, -1)

    @property
    def linear(self) -> bool:
        return self.coefficients is not None

    @property
    def dependencies(self) -> frozenset[Predicate]:
        return frozenset()

    def concretizations(self, constants: dict[str, tuple[str, ...]]) -> tuple["ArithmeticLiteral", ...]:
        return (self,)

    def instantiate(self, variables: Iterator[str]) -> ast.AST:
        expression = mode_terms.instantiate(self.expression, variables)
        output = mode_terms.instantiate(self.output, variables)
        return comparison([expression, output], ("=",))


def _linear_coefficients(
    expression: ast.AST, multiplier: int
) -> tuple[int, ...] | None:
    if mode_terms.kind(expression) == "variable":
        return (multiplier,)
    if mode_terms.kind(expression) != "arithmetic" or mode_terms.value(expression) not in {"+", "-"}:
        return None
    left, right = mode_terms.arguments(expression)
    left_coefficients = _linear_coefficients(left, multiplier)
    right_coefficients = _linear_coefficients(
        right, multiplier if mode_terms.value(expression) == "+" else -multiplier
    )
    if left_coefficients is None or right_coefficients is None:
        return None
    return (*left_coefficients, *right_coefficients)
