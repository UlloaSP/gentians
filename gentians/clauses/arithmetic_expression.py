from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ArithmeticExpression:
    operator: str = ""
    arguments: tuple[ArithmeticExpression, ...] = ()
    variable: int | None = None
    constant: int | None = None
    symbol: str | None = None

    @classmethod
    def var(cls, variable: int) -> ArithmeticExpression:
        return cls(variable=variable)

    @classmethod
    def const(cls, constant: int) -> ArithmeticExpression:
        return cls(constant=constant)

    @classmethod
    def fixed(cls, symbol: str) -> ArithmeticExpression:
        return cls(symbol=symbol)

    @property
    def key(self) -> tuple[object, ...]:
        if self.variable is not None:
            return "var", self.variable
        if self.constant is not None:
            return "const", self.constant
        if self.symbol is not None:
            return "fixed", self.symbol
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
        return frozenset().union(*(argument.variables for argument in self.arguments))

    def _additive_terms(
        self,
        coefficient: int = 1,
    ) -> tuple[tuple[tuple[object, ...], int], ...]:
        if (
            self.variable is not None
            or self.constant is not None
            or self.symbol is not None
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
        if (
            self.variable is not None
            or self.constant is not None
            or self.symbol is not None
            or self.operator != "*"
        ):
            return (self.key,)
        return tuple(
            factor
            for argument in self.arguments
            for factor in argument._multiplicative_factors()
        )

    def remap(self, variables: dict[int, int]) -> ArithmeticExpression:
        if self.variable is not None:
            return ArithmeticExpression.var(variables[self.variable])
        if self.constant is not None or self.symbol is not None:
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
        if self.constant is not None or self.symbol is not None:
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
        if self.symbol is not None:
            return self.symbol
        if self.operator == "absolute":
            return f"|{self.arguments[0].render()}|"
        if self.operator in {"neg", "bitnot"}:
            symbol = "-" if self.operator == "neg" else "~"
            value = f"{symbol}{self.arguments[0].render(nested=True)}"
            return f"({value})" if nested else value
        if self.operator == "interval":
            left, right = self.arguments
            value = f"{left.render(nested=True)}..{right.render(nested=True)}"
            return f"({value})" if nested else value
        if self.operator.startswith("function:"):
            name = self.operator.removeprefix("function:")
            return f"{name}({','.join(arg.render() for arg in self.arguments)})"
        if self.operator == "tuple":
            values = ",".join(arg.render() for arg in self.arguments)
            suffix = "," if len(self.arguments) == 1 else ""
            return f"({values}{suffix})"
        left, right = self.arguments
        if self.operator == "abs":
            value = f"|{left.render(nested=True)}-{right.render(nested=True)}|"
        else:
            value = (
                f"{left.render(nested=True)}{self.operator}{right.render(nested=True)}"
            )
        return f"({value})" if nested and self.operator != "abs" else value
