from collections.abc import Set
from functools import lru_cache
from math import gcd

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


@lru_cache(maxsize=1024)
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
    coefficients = [0 for _ in range(width)]
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


@lru_cache(maxsize=1024)
def _comparison_linear_template(
    comparison: ComparisonLiteral,
) -> tuple[tuple[int, ...], int] | None:
    if comparison.default_negated or len(comparison.operators) != 1:
        return None
    position = 0

    def coefficients(
        term: TermTemplate,
    ) -> tuple[dict[int, int], int] | None:
        nonlocal position
        if term.kind == "variable":
            result = ({position: 1}, 0)
            position += 1
            return result
        if term.kind == "fixed":
            try:
                return {}, int(term.value)
            except ValueError:
                return None
        if term.kind != "arithmetic":
            return None
        if term.value in {"neg"}:
            value = coefficients(term.arguments[0])
            return None if value is None else _scale_linear(value, -1)
        if term.value not in {"+", "-", "*"}:
            return None
        left = coefficients(term.arguments[0])
        right = coefficients(term.arguments[1])
        if left is None or right is None:
            return None
        if term.value in {"+", "-"}:
            return _combine_linear(
                left, right, 1 if term.value == "+" else -1
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
    values, constant = _combine_linear(left, right, -1)
    return tuple(values.get(index, 0) for index in range(position)), constant


def _combine_linear(
    left: tuple[dict[int, int], int],
    right: tuple[dict[int, int], int],
    right_multiplier: int,
) -> tuple[dict[int, int], int]:
    values = dict(left[0])
    for position, coefficient in right[0].items():
        values[position] = (
            values.get(position, 0) + coefficient * right_multiplier
        )
    return values, left[1] + right[1] * right_multiplier


def _scale_linear(
    value: tuple[dict[int, int], int], multiplier: int
) -> tuple[dict[int, int], int]:
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
    """Normalize a connected system of linear ASP integer relations.

    Equality elimination uses integer cross-products followed by primitive-row
    reduction. It computes reduced row spaces without allocating rational
    coefficients: task arithmetic contains integer terms and constants, and a
    positive cross-product preserves the order of comparisons.
    """
    auxiliary = set(auxiliary_variables)
    rows = [
        (list(constraint.coefficients), constraint.relation)
        for constraint in constraints
    ]
    while auxiliary:
        pivot = next(
            (
                (index, variable)
                for variable in sorted(auxiliary)
                for index, (coefficients, relation) in enumerate(rows)
                if relation == "eq" and abs(coefficients[variable]) == 1
            ),
            None,
        )
        if pivot is None:
            break
        pivot_index, variable = pivot
        equation, _relation = rows.pop(pivot_index)
        divisor = equation[variable]
        reduced: list[tuple[list[int], str]] = []
        for coefficients, relation in rows:
            factor = coefficients[variable] // divisor
            reduced.append(
                (
                    [
                        value - factor * equation_value
                        for value, equation_value in zip(coefficients, equation)
                    ],
                    relation,
                )
            )
        rows = reduced
        auxiliary.remove(variable)

    equations = _integer_rref(
        [tuple(row) for row, relation in rows if relation == "eq"], width
    )
    comparisons = [
        (tuple(row), relation) for row, relation in rows if relation != "eq"
    ]
    for equation in equations:
        pivot = next(index for index, value in enumerate(equation) if value)
        pivot_value = equation[pivot]
        comparisons = [
            (
                tuple(
                    value * pivot_value - coefficients[pivot] * equation_value
                    for value, equation_value in zip(coefficients, equation)
                ),
                relation,
            )
            for coefficients, relation in comparisons
        ]

    normalized: set[LinearConstraint] = {
        LinearConstraint(_primitive_row(row, True), "eq")
        for row in equations
    }
    for row, relation in comparisons:
        coefficients = _primitive_row(row, relation == "ne")
        if not any(coefficients):
            if relation in {"lt", "ne"}:
                return None
            continue
        normalized.add(LinearConstraint(coefficients, relation))
    return _finish_normalization(normalized)


def _integer_rref(
    rows: list[tuple[int, ...]], width: int
) -> tuple[tuple[int, ...], ...]:
    matrix = [list(_primitive_row(row, True)) for row in rows if any(row)]
    pivot_row = 0
    for column in range(width):
        pivot = next(
            (row for row in range(pivot_row, len(matrix)) if matrix[row][column]),
            None,
        )
        if pivot is None:
            continue
        matrix[pivot_row], matrix[pivot] = matrix[pivot], matrix[pivot_row]
        pivot_values = matrix[pivot_row]
        pivot_value = pivot_values[column]
        for row, values in enumerate(matrix):
            if row == pivot_row or not values[column]:
                continue
            factor = values[column]
            matrix[row] = list(
                _primitive_row(
                    tuple(
                        value * pivot_value - factor * pivot_coefficient
                        for value, pivot_coefficient in zip(values, pivot_values)
                    ),
                    True,
                )
            )
        pivot_row += 1
        if pivot_row == len(matrix):
            break
    return tuple(tuple(row) for row in matrix if any(row))


def _finish_normalization(
    normalized: set[LinearConstraint],
) -> tuple[LinearConstraint, ...] | None:
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


@lru_cache(maxsize=8192)
def _primitive_row(
    coefficients: tuple[int, ...], allow_sign_flip: bool
) -> tuple[int, ...]:
    divisor = 0
    for value in coefficients:
        divisor = gcd(divisor, abs(value))
    if divisor > 1:
        coefficients = tuple(value // divisor for value in coefficients)
    first = next((value for value in coefficients if value), 0)
    if allow_sign_flip and first < 0:
        return tuple(-value for value in coefficients)
    return coefficients


def _constraint_key(constraint: LinearConstraint) -> tuple[object, ...]:
    order = {"eq": 0, "lt": 1, "le": 2, "ne": 3}
    return order[constraint.relation], constraint.coefficients
