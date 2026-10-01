"""Clingo node constructors shared by the language-bias IR."""

from collections.abc import Iterable, Iterator

import clingo
from clingo import ast

LOCATION = ast.Location(
    ast.Position("<gentians>", 1, 1), ast.Position("<gentians>", 1, 1)
)

COMPARISON_OPERATORS = {
    "=": ast.ComparisonOperator.Equal,
    "!=": ast.ComparisonOperator.NotEqual,
    "<": ast.ComparisonOperator.LessThan,
    "<=": ast.ComparisonOperator.LessEqual,
    ">": ast.ComparisonOperator.GreaterThan,
    ">=": ast.ComparisonOperator.GreaterEqual,
}
BINARY_OPERATORS = {
    "+": ast.BinaryOperator.Plus,
    "-": ast.BinaryOperator.Minus,
    "*": ast.BinaryOperator.Multiplication,
    "/": ast.BinaryOperator.Division,
    "\\": ast.BinaryOperator.Modulo,
    "**": ast.BinaryOperator.Power,
    "&": ast.BinaryOperator.And,
    "?": ast.BinaryOperator.Or,
    "^": ast.BinaryOperator.XOr,
}
UNARY_OPERATORS = {
    "neg": ast.UnaryOperator.Minus,
    "bitnot": ast.UnaryOperator.Negation,
    "absolute": ast.UnaryOperator.Absolute,
}
AGGREGATE_FUNCTIONS = {
    "count": ast.AggregateFunction.Count,
    "sum": ast.AggregateFunction.Sum,
    "sum+": ast.AggregateFunction.SumPlus,
    "min": ast.AggregateFunction.Min,
    "max": ast.AggregateFunction.Max,
}


def binding_term(value: str) -> ast.AST:
    """Instantiate a binding as a variable or a ground validation value."""
    if value[0].isupper() or value.startswith("_"):
        return ast.Variable(LOCATION, value)
    return ast.SymbolicTerm(LOCATION, clingo.parse_term(value))


def binding_terms(values: Iterable[str]) -> Iterator[ast.AST]:
    """Share repeated bindings within this instantiation, including probe values."""
    nodes: dict[str, ast.AST] = {}
    for value in values:
        node = nodes.get(value)
        if node is None:
            node = binding_term(value)
            nodes[value] = node
        yield node


def literal(atom: ast.AST, negated: bool = False, double: bool = False) -> ast.AST:
    sign = (
        ast.Sign.DoubleNegation if double else
        ast.Sign.Negation if negated else ast.Sign.NoSign
    )
    return ast.Literal(LOCATION, sign, atom)


def operation(operator: str, arguments: list[ast.AST]) -> ast.AST:
    if operator in UNARY_OPERATORS:
        return ast.UnaryOperation(LOCATION, UNARY_OPERATORS[operator], arguments[0])
    if operator == "abs":
        difference = ast.BinaryOperation(LOCATION, ast.BinaryOperator.Minus, *arguments)
        return ast.UnaryOperation(LOCATION, ast.UnaryOperator.Absolute, difference)
    if operator == "interval":
        return ast.Interval(LOCATION, *arguments)
    return ast.BinaryOperation(LOCATION, BINARY_OPERATORS[operator], *arguments)


def comparison(
    terms: list[ast.AST], operators: tuple[str, ...],
    negated: bool = False, double: bool = False,
) -> ast.AST:
    return literal(ast.Comparison(terms[0], [
        ast.Guard(COMPARISON_OPERATORS[operator], term)
        for operator, term in zip(operators, terms[1:], strict=True)
    ]), negated, double)


def consume_all(variables: Iterator[ast.AST]) -> None:
    if next(variables, None) is not None:
        raise ValueError("literal has more variables than syntax bindings")
