from collections.abc import Iterator
from dataclasses import dataclass, field

from clingo import ast

from ..language import terms as mode_terms
from ..language.asp import Predicate
from ..language.ast_nodes import comparison


@dataclass(frozen=True, slots=True)
class ArithmeticLiteral:
    expression: ast.AST
    output: ast.AST
    implicit_additive_family_member: bool = field(
        default=False, repr=False
    )
    # A derived non-None result always includes the output coefficient.
    _coefficients: tuple[int, ...] | None = field(default=(), init=False, repr=False, compare=False)

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
        cached = self._coefficients
        if cached == ():
            coefficients = _linear_coefficients(self.expression, 1)
            cached = None if coefficients is None else (*coefficients, -1)
            object.__setattr__(self, "_coefficients", cached)
        return cached

    @property
    def linear(self) -> bool:
        return self.coefficients is not None

    @property
    def dependencies(self) -> frozenset[Predicate]:
        return frozenset()

    def concretizations(self, constants: dict[str, tuple[ast.AST, ...]]) -> Iterator["ArithmeticLiteral"]:
        return iter((self,))

    def instantiate(self, variables: Iterator[ast.AST]) -> ast.AST:
        expression = mode_terms.instantiate(self.expression, variables)
        output = mode_terms.instantiate(self.output, variables)
        return comparison([expression, output], ("=",))


def _linear_coefficients(
    expression: ast.AST, multiplier: int
) -> tuple[int, ...] | None:
    pending = [(expression, multiplier)]
    coefficients = []
    while pending:
        node, factor = pending.pop()
        if mode_terms.kind(node) == "variable":
            coefficients.append(factor)
            continue
        if mode_terms.kind(node) != "arithmetic" or mode_terms.value(node) not in {"+", "-"}:
            return None
        left, right = mode_terms.arguments(node)
        pending.append((right, factor if mode_terms.value(node) == "+" else -factor))
        pending.append((left, factor))
    return tuple(coefficients)
