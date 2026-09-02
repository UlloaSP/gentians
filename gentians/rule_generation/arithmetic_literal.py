from collections.abc import Iterator
from dataclasses import dataclass

from .parser import Predicate
from .term_template import TermTemplate


@dataclass(frozen=True, slots=True)
class ArithmeticLiteral:
    expression: TermTemplate
    output: TermTemplate
    complexity: int = 1

    def __post_init__(self) -> None:
        if self.expression.kind != "arithmetic" or len(self.expression.arguments) != 2:
            raise ValueError(
                "arithmetic literals require a binary arithmetic expression"
            )

    @property
    def kind(self) -> str:
        return "arithmetic"

    @property
    def arguments(self) -> tuple[TermTemplate, ...]:
        return (*self.expression.arguments, self.output)

    @property
    def operator(self) -> str:
        return self.expression.value

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

    def render(self, variables: Iterator[str]) -> str:
        expression = self.expression.render(variables)
        return f"{expression}={self.output.render(variables)}"


def _linear_coefficients(
    expression: TermTemplate, multiplier: int
) -> tuple[int, ...] | None:
    if expression.kind == "variable":
        return (multiplier,)
    if expression.kind != "arithmetic" or expression.value not in {"+", "-"}:
        return None
    left, right = expression.arguments
    left_coefficients = _linear_coefficients(left, multiplier)
    right_coefficients = _linear_coefficients(
        right, multiplier if expression.value == "+" else -multiplier
    )
    if left_coefficients is None or right_coefficients is None:
        return None
    return (*left_coefficients, *right_coefficients)
