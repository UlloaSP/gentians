from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ArithmeticExpression:
    operator: str = ""
    arguments: tuple[ArithmeticExpression, ...] = ()
    variable: int | None = None
    constant: int | None = None

    @classmethod
    def var(cls, variable: int) -> ArithmeticExpression:
        return cls(variable=variable)

    @classmethod
    def const(cls, constant: int) -> ArithmeticExpression:
        return cls(constant=constant)

    @property
    def key(self) -> tuple[object, ...]:
        if self.variable is not None:
            return "var", self.variable
        if self.constant is not None:
            return "const", self.constant
        if self.operator in {"+", "-"}:
            coefficients: dict[tuple[object, ...], int] = {}
            for key, coefficient in self._additive_terms():
                coefficients[key] = coefficients.get(key, 0) + coefficient
            return "sum", tuple(
                sorted(
                    (
                        (key, coefficient)
                        for key, coefficient in coefficients.items()
                        if coefficient
                    ),
                    key=repr,
                )
            )
        if self.operator == "*":
            factors = self._multiplicative_factors()
            return "product", tuple(sorted(factors, key=repr))
        keys = tuple(argument.key for argument in self.arguments)
        if self.operator == "abs":
            keys = tuple(sorted(keys, key=repr))
        return self.operator, keys

    @property
    def variables(self) -> frozenset[int]:
        if self.variable is not None:
            return frozenset((self.variable,))
        return frozenset().union(
            *(argument.variables for argument in self.arguments)
        )

    def _additive_terms(
        self,
        coefficient: int = 1,
    ) -> tuple[tuple[tuple[object, ...], int], ...]:
        if (
            self.variable is not None
            or self.constant is not None
            or self.operator not in {"+", "-"}
        ):
            return ((self.key, coefficient),)
        left, right = self.arguments
        right_coefficient = coefficient if self.operator == "+" else -coefficient
        return (
            *left._additive_terms(coefficient),
            *right._additive_terms(right_coefficient),
        )

    def _multiplicative_factors(self) -> tuple[tuple[object, ...], ...]:
        if self.variable is not None or self.constant is not None or self.operator != "*":
            return (self.key,)
        return tuple(
            factor
            for argument in self.arguments
            for factor in argument._multiplicative_factors()
        )

    def remap(self, variables: dict[int, int]) -> ArithmeticExpression:
        if self.variable is not None:
            return ArithmeticExpression.var(variables[self.variable])
        if self.constant is not None:
            return self
        return ArithmeticExpression(
            self.operator,
            tuple(argument.remap(variables) for argument in self.arguments),
        )

    def substitute(
        self, variables: dict[int, ArithmeticExpression]
    ) -> ArithmeticExpression:
        if self.variable is not None:
            return variables.get(self.variable, self)
        if self.constant is not None:
            return self
        return ArithmeticExpression(
            self.operator,
            tuple(argument.substitute(variables) for argument in self.arguments),
        )

    def render(self, *, nested: bool = False) -> str:
        if self.variable is not None:
            return f"V{self.variable}"
        if self.constant is not None:
            return str(self.constant)
        left, right = self.arguments
        if self.operator == "abs":
            value = (
                f"|{left.render(nested=True)}-"
                f"{right.render(nested=True)}|"
            )
        else:
            value = f"{left.render(nested=True)}{self.operator}{right.render(nested=True)}"
        return f"({value})" if nested and self.operator != "abs" else value
