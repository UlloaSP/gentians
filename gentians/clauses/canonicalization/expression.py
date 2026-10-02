from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from functools import lru_cache
from typing import cast

import clingo
from clingo import ast

from ...language.ast_nodes import LOCATION, binding_term, operation


@dataclass(frozen=True, slots=True, eq=False)
class ArithmeticExpression:
    operator: str = ""
    arguments: tuple["ArithmeticExpression", ...] = ()
    variable: int | None = None
    constant: int | None = None
    symbol: str | None = None
    _hash: int = field(init=False, repr=False)
    _variables: frozenset[int] | None = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_hash", hash((
            self.operator, tuple(hash(argument) for argument in self.arguments),
            self.variable, self.constant, self.symbol,
        )))

    def __hash__(self) -> int:
        return self._hash

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ArithmeticExpression):
            return NotImplemented
        pending: list[tuple[ArithmeticExpression, ArithmeticExpression]] = [(self, other)]
        compared: set[tuple[int, int]] = set()
        while pending:
            left, right = pending.pop()
            pair = id(left), id(right)
            if left is right or pair in compared:
                continue
            if (left.operator, left.variable, left.constant, left.symbol, len(left.arguments)) != (
                right.operator, right.variable, right.constant, right.symbol, len(right.arguments)
            ):
                return False
            compared.add(pair)
            pending.extend(zip(left.arguments, right.arguments, strict=True))
        return True

    @classmethod
    def var(cls, variable: int) -> "ArithmeticExpression":
        return cls(variable=variable)

    @classmethod
    def const(cls, constant: int) -> "ArithmeticExpression":
        return cls(constant=constant)

    @classmethod
    def fixed(cls, symbol: str) -> "ArithmeticExpression":
        return cls(symbol=symbol)

    @property
    def key(self) -> tuple[object, ...]:
        return _expression_key(self)

    @property
    def variables(self) -> frozenset[int]:
        variables = self._variables
        if variables is None:
            result: set[int] = set()
            for node in _postorder(self):
                if node.variable is not None:
                    result.add(node.variable)
            variables = frozenset(result)
            object.__setattr__(self, "_variables", variables)
        return variables

    def _transform(self, replace: Callable[["ArithmeticExpression"], "ArithmeticExpression"]) -> "ArithmeticExpression":
        results: dict[int, ArithmeticExpression] = {}
        for node in _postorder(self):
            children = tuple(results[id(child)] for child in node.arguments)
            if node.variable is not None:
                result = replace(node)
            elif all(child is original for child, original in zip(children, node.arguments, strict=True)):
                result = node
            else:
                result = ArithmeticExpression(node.operator, children)
            results[id(node)] = result
        return results[id(self)]

    def remap(self, variables: dict[int, int]) -> "ArithmeticExpression":
        def replace(node: ArithmeticExpression) -> ArithmeticExpression:
            assert node.variable is not None
            variable = variables[node.variable]
            return node if variable == node.variable else ArithmeticExpression.var(variable)

        return self._transform(replace)

    def substitute(self, variables: dict[int, "ArithmeticExpression"]) -> "ArithmeticExpression":
        def replace(node: ArithmeticExpression) -> ArithmeticExpression:
            assert node.variable is not None
            return variables.get(node.variable, node)

        return self._transform(replace)

    def instantiate(self) -> ast.AST:
        results: dict[int, ast.AST] = {}
        for node in _postorder(self):
            arguments = [results[id(child)] for child in node.arguments]
            if node.variable is not None:
                result = binding_term(f"V{node.variable}")
            elif node.constant is not None:
                result = _integer_term(node.constant)
            elif node.symbol is not None:
                result = ast.SymbolicTerm(LOCATION, clingo.parse_term(node.symbol))
            elif node.operator.startswith("function:"):
                result = ast.Function(LOCATION, node.operator.removeprefix("function:"), arguments, False)
            elif node.operator == "tuple":
                result = ast.Function(LOCATION, "", arguments, False)
            else:
                result = operation("*" if node.operator == "scale" else node.operator, arguments)
            results[id(node)] = result
        return results[id(self)]

    def render(self) -> str:
        return str(self.instantiate())


def _integer_term(value: int) -> ast.AST:
    """Express oversized exact coefficients using native integer leaves."""
    if -(2**31) <= value < 2**31:
        return ast.SymbolicTerm(LOCATION, clingo.Number(value))
    radix = 2**30
    digits: list[int] = []
    remaining = abs(value)
    while remaining:
        remaining, digit = divmod(remaining, radix)
        digits.append(digit)
    result = ast.SymbolicTerm(LOCATION, clingo.Number(digits.pop()))
    factor = ast.SymbolicTerm(LOCATION, clingo.Number(radix))
    while digits:
        result = operation("*", [result, factor])
        if digit := digits.pop():
            result = operation("+", [result, ast.SymbolicTerm(LOCATION, clingo.Number(digit))])
    return operation("neg", [result]) if value < 0 else result


def _postorder(expression: ArithmeticExpression) -> Iterator[ArithmeticExpression]:
    """Visit shared immutable subexpressions once, after their children."""
    pending = [(expression, False)]
    completed: set[int] = set()
    while pending:
        node, visited = pending.pop()
        if id(node) in completed:
            continue
        children = () if node.variable is not None or node.constant is not None or node.symbol is not None else node.arguments
        if visited or not children:
            completed.add(id(node))
            yield node
        else:
            pending.append((node, True))
            pending.extend((child, False) for child in reversed(children))


@lru_cache(maxsize=8192)
def _expression_key(expression: ArithmeticExpression) -> tuple[object, ...]:
    """Normalize keys bottom-up; expression hashing and equality are iterative."""
    results: dict[int, tuple[object, ...]] = {}
    for node in _postorder(expression):
        children = tuple(results[id(child)] for child in node.arguments)
        if node.variable is not None:
            key = "var", node.variable
        elif node.constant is not None:
            key = "const", node.constant
        elif node.symbol is not None:
            key = "fixed", node.symbol
        elif node.operator in {"+", "-", "scale"}:
            coefficients: dict[tuple[object, ...], int] = {}
            if node.operator == "scale":
                coefficient = node.arguments[0].constant
                assert coefficient is not None
                terms_to_add = ((children[1], coefficient),)
            else:
                terms_to_add = tuple(zip(children, (1, 1 if node.operator == "+" else -1), strict=True))
            for child, multiplier in terms_to_add:
                terms = cast(tuple[tuple[tuple[object, ...], int], ...], child[1]) if child[0] == "sum" else ((child, 1),)
                for term, coefficient in terms:
                    coefficients[term] = coefficients.get(term, 0) + coefficient * multiplier
            key = "sum", tuple(sorted(((term, coefficient) for term, coefficient in coefficients.items() if coefficient), key=repr))
        elif node.operator == "*":
            factors = tuple(factor for child in children for factor in (cast(tuple[tuple[object, ...], ...], child[1]) if child[0] == "product" else (child,)))
            key = "product", tuple(sorted(factors, key=repr))
        else:
            key = node.operator, tuple(sorted(children, key=repr)) if node.operator == "abs" else children
        results[id(node)] = key
    return results[id(expression)]
