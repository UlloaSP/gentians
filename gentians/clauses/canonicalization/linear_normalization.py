from collections.abc import Set
from fractions import Fraction
from functools import lru_cache
from math import gcd, lcm

from ...language.ir.arithmetic_literal import ArithmeticLiteral
from ...language.ir.comparison_literal import ComparisonLiteral
from ...language.ir.term_template import TermTemplate
from ..clause_mode import ClauseMode
from ..reified_literal import ReifiedLiteral
from .arithmetic_system import SystemRelation
from .expression import ArithmeticExpression
from .expression_constraint import ExpressionConstraint
from .linear_constraint import LinearConstraint


def _orient_linear_constraints(
    constraints: tuple[LinearConstraint, ...],
    initially_safe: Set[int],
) -> tuple[SystemRelation, ...] | None:
    safe = set(initially_safe)
    pending = list(constraints)
    oriented: list[SystemRelation] = []
    while pending:
        ready = next(
            (constraint for constraint in pending if not (constraint.variables - safe)),
            None,
        )
        if ready is not None:
            oriented.append(ready)
            pending.remove(ready)
            continue
        assignment = next(
            (
                (constraint, next(iter(constraint.variables - safe)))
                for constraint in pending
                if constraint.relation == "eq"
                and len(constraint.variables - safe) == 1
                and abs(
                    constraint.coefficients[next(iter(constraint.variables - safe))]
                )
                == 1
            ),
            None,
        )
        if assignment is None:
            return None
        constraint, output = assignment
        oriented.append(
            ExpressionConstraint(
                _linear_assignment_expression(constraint, output),
                "eq",
                output,
                False,
            )
        )
        safe.add(output)
        pending.remove(constraint)
    return tuple(oriented)


def _linear_assignment_expression(
    constraint: LinearConstraint, output: int
) -> ArithmeticExpression:
    divisor = constraint.coefficients[output]
    positive: list[ArithmeticExpression] = []
    negative: list[ArithmeticExpression] = []
    for variable, coefficient in enumerate(constraint.coefficients):
        if variable == output or not coefficient:
            continue
        scaled = int(-coefficient / divisor)
        target = positive if scaled > 0 else negative
        target.extend(ArithmeticExpression.var(variable) for _ in range(abs(scaled)))
    expression = (
        _fold_expression("+", positive) if positive else ArithmeticExpression.const(0)
    )
    for value in negative:
        expression = ArithmeticExpression("-", (expression, value))
    return expression


def _fold_expression(
    operator: str,
    expressions: list[ArithmeticExpression],
) -> ArithmeticExpression:
    result = expressions[0]
    for expression in expressions[1:]:
        result = ArithmeticExpression(operator, (result, expression))
    return result


def _is_linear(mode: ClauseMode, allow_disequality: bool) -> bool:
    syntax = mode.literal
    comparison_linear = (
        _comparison_linear_template(syntax)
        if isinstance(syntax, ComparisonLiteral)
        else None
    )
    return (isinstance(syntax, ArithmeticLiteral) and syntax.linear) or (
        isinstance(syntax, ComparisonLiteral)
        and comparison_linear is not None
        and comparison_linear[1] == 0
        and (
            syntax.operators[0] in {"<", "<=", ">", ">="}
            or syntax.operators[0] == "="
            or (allow_disequality and syntax.operators[0] == "!=")
        )
    )


@lru_cache(maxsize=8192)
def _constraint(
    literal: ReifiedLiteral,
    mode: ClauseMode,
    width: int,
) -> LinearConstraint:
    coefficients = [Fraction(0) for _ in range(width)]
    if isinstance(mode.literal, ArithmeticLiteral):
        arithmetic = mode.literal
        if arithmetic.linear:
            assert arithmetic.coefficients is not None
            for variable, coefficient in zip(
                literal.variables, arithmetic.coefficients
            ):
                coefficients[variable] += coefficient
            return LinearConstraint(tuple(coefficients), "eq")
        raise ValueError(f"arithmetic mode {mode.id} is not linear")

    if not isinstance(mode.literal, ComparisonLiteral):
        raise ValueError(f"comparison mode {mode.id} has no template")
    template = _comparison_linear_template(mode.literal)
    if template is None:
        raise ValueError(f"comparison mode {mode.id} is not linear")
    template_coefficients, constant = template
    if constant:
        raise ValueError("linear constraint constants must cancel")
    for variable, coefficient in zip(
        literal.variables, template_coefficients, strict=True
    ):
        coefficients[variable] += coefficient
    operator = mode.literal.operators[0]
    if operator in {">", ">="}:
        coefficients = [-coefficient for coefficient in coefficients]
        operator = "<" if operator == ">" else "<="
    relation = {"=": "eq", "<": "lt", "<=": "le", "!=": "ne"}[operator]
    return LinearConstraint(tuple(coefficients), relation)


def _comparison_linear_template(
    comparison: ComparisonLiteral,
) -> tuple[tuple[Fraction, ...], Fraction] | None:
    if comparison.default_negated or len(comparison.operators) != 1:
        return None
    position = 0

    def coefficients(
        term: TermTemplate,
    ) -> tuple[dict[int, Fraction], Fraction] | None:
        nonlocal position
        if term.kind == "variable":
            result = ({position: Fraction(1)}, Fraction(0))
            position += 1
            return result
        if term.kind == "fixed":
            try:
                return {}, Fraction(int(term.value))
            except ValueError:
                return None
        if term.kind != "arithmetic":
            return None
        if term.value in {"neg"}:
            value = coefficients(term.arguments[0])
            return None if value is None else _scale_linear(value, Fraction(-1))
        if term.value not in {"+", "-", "*"}:
            return None
        left = coefficients(term.arguments[0])
        right = coefficients(term.arguments[1])
        if left is None or right is None:
            return None
        if term.value in {"+", "-"}:
            return _combine_linear(
                left, right, Fraction(1 if term.value == "+" else -1)
            )
        left_variables, left_constant = left
        right_variables, right_constant = right
        if not left_variables:
            return _scale_linear(right, left_constant)
        if not right_variables:
            return _scale_linear(left, right_constant)
        return None

    left = coefficients(comparison.terms[0])
    right = coefficients(comparison.terms[1])
    if left is None or right is None:
        return None
    values, constant = _combine_linear(left, right, Fraction(-1))
    return tuple(values.get(index, Fraction(0)) for index in range(position)), constant


def _combine_linear(
    left: tuple[dict[int, Fraction], Fraction],
    right: tuple[dict[int, Fraction], Fraction],
    right_multiplier: Fraction,
) -> tuple[dict[int, Fraction], Fraction]:
    values = dict(left[0])
    for position, coefficient in right[0].items():
        values[position] = (
            values.get(position, Fraction(0)) + coefficient * right_multiplier
        )
    return values, left[1] + right[1] * right_multiplier


def _scale_linear(
    value: tuple[dict[int, Fraction], Fraction], multiplier: Fraction
) -> tuple[dict[int, Fraction], Fraction]:
    return (
        {
            position: coefficient * multiplier
            for position, coefficient in value[0].items()
        },
        value[1] * multiplier,
    )


@lru_cache(maxsize=8192)
def _normalize_component(
    constraints: tuple[LinearConstraint, ...],
    auxiliary_variables: frozenset[int],
    width: int,
) -> tuple[LinearConstraint, ...] | None:
    auxiliary = set(auxiliary_variables)
    rows = list(constraints)
    while auxiliary:
        pivot = next(
            (
                (index, variable)
                for variable in sorted(auxiliary)
                for index, constraint in enumerate(rows)
                if constraint.relation == "eq"
                and abs(constraint.coefficients[variable]) == 1
            ),
            None,
        )
        if pivot is None:
            break
        pivot_index, variable = pivot
        equation = rows.pop(pivot_index)
        divisor = equation.coefficients[variable]
        reduced: list[LinearConstraint] = []
        for constraint in rows:
            factor = constraint.coefficients[variable] / divisor
            coefficients = tuple(
                value - factor * equation_value
                for value, equation_value in zip(
                    constraint.coefficients, equation.coefficients
                )
            )
            reduced.append(LinearConstraint(coefficients, constraint.relation))
        rows = reduced
        auxiliary.remove(variable)

    equations = _rref(
        [constraint.coefficients for constraint in rows if constraint.relation == "eq"],
        width,
    )
    comparisons = [constraint for constraint in rows if constraint.relation != "eq"]
    for equation in equations:
        pivot = next(index for index, value in enumerate(equation) if value)
        reduced = []
        for comparison in comparisons:
            factor = comparison.coefficients[pivot] / equation[pivot]
            coefficients = tuple(
                value - factor * equation_value
                for value, equation_value in zip(comparison.coefficients, equation)
            )
            reduced.append(LinearConstraint(coefficients, comparison.relation))
        comparisons = reduced

    normalized: set[LinearConstraint] = {
        LinearConstraint(_primitive(row, allow_sign_flip=True), "eq")
        for row in equations
    }
    for comparison in comparisons:
        coefficients = _primitive(
            comparison.coefficients,
            allow_sign_flip=comparison.relation == "ne",
        )
        if not any(coefficients):
            if comparison.relation in {"lt", "ne"}:
                return None
            continue
        normalized.add(LinearConstraint(coefficients, comparison.relation))

    equalities = {
        constraint.coefficients
        for constraint in normalized
        if constraint.relation == "eq"
    }
    if any(
        constraint.coefficients in equalities and constraint.relation in {"lt", "ne"}
        for constraint in normalized
    ):
        return None
    normalized = {
        constraint
        for constraint in normalized
        if not (constraint.coefficients in equalities and constraint.relation == "le")
    }
    strict = {
        constraint.coefficients
        for constraint in normalized
        if constraint.relation == "lt"
    }
    normalized = {
        constraint
        for constraint in normalized
        if not (
            constraint.coefficients in strict and constraint.relation in {"le", "ne"}
        )
    }
    return tuple(sorted(normalized, key=_constraint_key))


def _rref(
    rows: list[tuple[Fraction, ...]],
    width: int,
) -> tuple[tuple[Fraction, ...], ...]:
    matrix = [list(row) for row in rows]
    pivot_row = 0
    for column in range(width):
        pivot = next(
            (row for row in range(pivot_row, len(matrix)) if matrix[row][column]),
            None,
        )
        if pivot is None:
            continue
        matrix[pivot_row], matrix[pivot] = matrix[pivot], matrix[pivot_row]
        divisor = matrix[pivot_row][column]
        matrix[pivot_row] = [value / divisor for value in matrix[pivot_row]]
        for row, values in enumerate(matrix):
            if row == pivot_row or not values[column]:
                continue
            factor = values[column]
            matrix[row] = [
                value - factor * pivot_value
                for value, pivot_value in zip(values, matrix[pivot_row])
            ]
        pivot_row += 1
        if pivot_row == len(matrix):
            break
    return tuple(tuple(row) for row in matrix if any(row))


@lru_cache(maxsize=8192)
def _primitive(
    coefficients: tuple[Fraction, ...],
    *,
    allow_sign_flip: bool,
) -> tuple[Fraction, ...]:
    denominator = 1
    for coefficient in coefficients:
        denominator = lcm(denominator, coefficient.denominator)
    integers = [int(coefficient * denominator) for coefficient in coefficients]
    divisor = 0
    for value in integers:
        divisor = gcd(divisor, abs(value))
    if divisor:
        integers = [value // divisor for value in integers]
    first = next((value for value in integers if value), 0)
    if allow_sign_flip and first < 0:
        integers = [-value for value in integers]
    return tuple(Fraction(value) for value in integers)


def _constraint_key(constraint: LinearConstraint) -> tuple[object, ...]:
    order = {"eq": 0, "lt": 1, "le": 2, "ne": 3}
    return order[constraint.relation], constraint.coefficients
