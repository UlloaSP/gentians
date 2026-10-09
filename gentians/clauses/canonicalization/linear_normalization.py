from functools import lru_cache
from heapq import heappop, heappush
from math import gcd

from clingo import ast

from ...language import terms as mode_terms
from ..arithmetic_literal import ArithmeticLiteral
from ...language.ir.comparison_literal import ComparisonLiteral
from ..clause_mode import ClauseMode
from .arithmetic_system import SystemRelation
from .expression import ArithmeticExpression
from .expression_constraint import ExpressionConstraint
from .linear_constraint import LinearConstraint


def _orient_linear_constraints(
    constraints: tuple[LinearConstraint, ...],
    initially_safe: int,
) -> tuple[SystemRelation, ...] | None:
    variables = tuple(constraint.variable_mask for constraint in constraints)
    if all(not used & ~initially_safe for used in variables):
        return constraints
    missing = [used & ~initially_safe for used in variables]
    waiting: dict[int, list[int]] = {}
    ready: list[int] = []
    assignments: list[int] = []
    active = [True] * len(constraints)
    oriented: list[SystemRelation] = []

    def enqueue(index: int) -> None:
        if not missing[index]:
            heappush(ready, index)
        elif (missing[index].bit_count() == 1 and constraints[index].relation == "eq"
              and abs(constraints[index].coefficients[missing[index].bit_length() - 1]) == 1):
            heappush(assignments, index)

    for index, unknown in enumerate(missing):
        enqueue(index)
        while unknown:
            bit = unknown & -unknown
            variable = bit.bit_length() - 1
            unknown ^= bit
            waiting.setdefault(variable, []).append(index)
    while len(oriented) < len(constraints):
        while ready and not active[ready[0]]:
            heappop(ready)
        if ready:
            index = heappop(ready)
            oriented.append(constraints[index])
            active[index] = False
            continue
        while assignments and (not active[assignments[0]] or missing[assignments[0]].bit_count() != 1):
            heappop(assignments)
        if not assignments:
            return None
        index = heappop(assignments)
        constraint = constraints[index]
        output = missing[index].bit_length() - 1
        oriented.append(ExpressionConstraint(
            _linear_assignment_expression(constraint, output), "eq", output, False,
        ))
        active[index] = False
        for consumer in waiting.pop(output, ()):
            if active[consumer]:
                missing[consumer] &= ~(1 << output)
                enqueue(consumer)
    return tuple(oriented)


def _linear_assignment_expression(
    constraint: LinearConstraint, output: int
) -> ArithmeticExpression:
    divisor = constraint.coefficients[output]
    assert abs(divisor) == 1
    positive: list[ArithmeticExpression] = []
    negative: list[ArithmeticExpression] = []
    for variable, coefficient in enumerate(constraint.coefficients):
        if variable == output or not coefficient:
            continue
        scaled = -coefficient // divisor
        target = positive if scaled > 0 else negative
        term = ArithmeticExpression.var(variable)
        if scaled == -2:
            target.extend((term, term))
            continue
        if abs(scaled) == 2:
            term = ArithmeticExpression("+", (term, term))
        elif abs(scaled) > 2:
            term = ArithmeticExpression("scale", (ArithmeticExpression.const(abs(scaled)), term))
        target.append(term)
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
    variables: tuple[int, ...],
    mode: ClauseMode,
    width: int,
) -> LinearConstraint:
    coefficients = [0 for _ in range(width)]
    if isinstance(mode.literal, ArithmeticLiteral):
        arithmetic = mode.literal
        if arithmetic.linear:
            assert arithmetic.coefficients is not None
            for variable, coefficient in zip(variables, arithmetic.coefficients):
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
    for variable, coefficient in zip(variables, template_coefficients, strict=True):
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
        term: ast.AST,
    ) -> tuple[dict[int, int], int] | None:
        nonlocal position
        results: list[tuple[dict[int, int], int] | None] = []
        for node, count in mode_terms._postorder(term):
            children = results[-count:] if count else []
            if count:
                del results[-count:]
            kind = mode_terms.kind(node)
            value: tuple[dict[int, int], int] | None = None
            if kind == "variable":
                value = {position: 1}, 0
                position += 1
            elif kind == "fixed":
                try:
                    value = {}, int(mode_terms.value(node))
                except ValueError:
                    pass
            elif kind == "arithmetic":
                operator = mode_terms.value(node)
                if operator == "neg" and children[0] is not None:
                    value = _scale_linear(children[0], -1)
                elif operator in {"+", "-", "*"}:
                    left, right = children
                    if left is not None and right is not None:
                        if operator in {"+", "-"}:
                            value = _combine_linear(left, right, 1 if operator == "+" else -1)
                        elif not left[0]:
                            value = _scale_linear(right, left[1])
                        elif not right[0]:
                            value = _scale_linear(left, right[1])
            results.append(value)
        return results[0]

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
    auxiliary_variables: int,
    width: int,
) -> tuple[LinearConstraint, ...] | None:
    """Normalize a connected system of linear ASP integer relations.

    Equality elimination uses integer cross-products followed by primitive-row
    reduction. It computes reduced row spaces without allocating rational
    coefficients: task arithmetic contains integer terms and constants, and a
    positive cross-product preserves the order of comparisons.
    """
    if len(constraints) == 1:
        constraint = constraints[0]
        coefficients = constraint.coefficients
        if constraint.relation == "eq" and any(
            abs(coefficient) == 1 and auxiliary_variables & (1 << variable)
            for variable, coefficient in enumerate(coefficients)
        ):
            return ()
        coefficients = _primitive_row(coefficients, constraint.relation in {"eq", "ne"})
        if not any(coefficients):
            return None if constraint.relation in {"lt", "ne"} else ()
        return (
            constraint if coefficients == constraint.coefficients
            else LinearConstraint(coefficients, constraint.relation),
        )
    auxiliary = auxiliary_variables
    rows = [
        (list(constraint.coefficients), constraint.relation)
        for constraint in constraints
    ]
    while auxiliary:
        pivot = next(
            (
                (index, variable)
                for variable in range(width) if auxiliary & (1 << variable)
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
            if not factor:
                reduced.append((coefficients, relation))
                continue
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
        auxiliary &= ~(1 << variable)

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
                coefficients if not coefficients[pivot] else tuple(
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
    if len(rows) < 2:
        return (_primitive_row(rows[0], True),) if rows and any(rows[0]) else ()
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
    strict = {
        constraint.coefficients
        for constraint in normalized
        if constraint.relation == "lt"
    }
    return tuple(sorted((
        constraint
        for constraint in normalized
        if not (
            constraint.coefficients in equalities and constraint.relation == "le"
            or constraint.coefficients in strict and constraint.relation in {"le", "ne"}
        )
    ), key=_constraint_key))


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
