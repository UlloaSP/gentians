from concurrent.futures import InterpreterPoolExecutor
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from math import gcd, lcm
from os import process_cpu_count

from .hypothesis_mode import HypothesisMode
from .reified_clause import ReifiedClause
from .reified_literal import ReifiedLiteral

LinearClauseKey = tuple[object, ...]


def canonical_linear_clause_keys(
    clauses: list[ReifiedClause],
    modes: dict[int, HypothesisMode],
    max_variables: int,
) -> list[LinearClauseKey | None]:
    workers = min(4, process_cpu_count() or 1)
    if len(clauses) < 1000 or workers == 1:
        return [
            canonical_linear_clause_key(clause, modes, max_variables)
            for clause in clauses
        ]
    batch_size = (len(clauses) + workers - 1) // workers
    batches = [
        (clauses[start : start + batch_size], modes, max_variables)
        for start in range(0, len(clauses), batch_size)
    ]
    with InterpreterPoolExecutor(max_workers=workers) as executor:
        return [
            key
            for batch in executor.map(_canonical_key_batch, batches)
            for key in batch
        ]


def _canonical_key_batch(
    arguments: tuple[list[ReifiedClause], dict[int, HypothesisMode], int],
) -> list[LinearClauseKey | None]:
    clauses, modes, max_variables = arguments
    return [
        canonical_linear_clause_key(clause, modes, max_variables)
        for clause in clauses
    ]


@dataclass(frozen=True, slots=True)
class LinearConstraint:
    coefficients: tuple[Fraction, ...]
    relation: str

    @property
    def variables(self) -> frozenset[int]:
        return frozenset(
            index for index, coefficient in enumerate(self.coefficients) if coefficient
        )


def canonical_linear_clause_key(
    clause: ReifiedClause,
    modes: dict[int, HypothesisMode],
    max_variables: int,
) -> LinearClauseKey | None:
    builtin = [
        literal
        for literal in clause.body
        if modes[literal.mode_id].kind in {"arithmetic", "comparison"}
    ]
    if not any(
        modes[literal.mode_id].kind == "arithmetic"
        and modes[literal.mode_id].operator in {"+", "-"}
        for literal in builtin
    ):
        return _raw_clause_key(clause)
    if any(
        modes[literal.mode_id].kind == "arithmetic"
        and modes[literal.mode_id].operator not in {"+", "-"}
        for literal in builtin
    ):
        return _raw_clause_key(clause)

    parent = list(range(max_variables))

    def find(variable: int) -> int:
        while parent[variable] != variable:
            parent[variable] = parent[parent[variable]]
            variable = parent[variable]
        return variable

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for literal in builtin:
        for variable in literal.variables[1:]:
            union(literal.variables[0], variable)

    external = {
        variable
        for literal in (*clause.head, *clause.body)
        if modes[literal.mode_id].kind not in {"arithmetic", "comparison"}
        for variable in literal.variables
    }
    external.update(
        variable for literal in clause.head for variable in literal.variables
    )
    safe = {
        variable
        for literal in clause.body
        if modes[literal.mode_id].kind == "normal"
        and modes[literal.mode_id].positive
        for variable in literal.variables
    }
    safe.update(
        literal.variables[-1]
        for literal in clause.body
        if modes[literal.mode_id].kind == "aggregate"
    )

    components: dict[int, list[ReifiedLiteral]] = {}
    for literal in builtin:
        components.setdefault(find(literal.variables[0]), []).append(literal)

    replacements: list[tuple[object, ...]] = []
    for literals in components.values():
        if any(not _is_linear(modes[literal.mode_id]) for literal in literals):
            replacements.append(
                (
                    "raw",
                    tuple(_literal_key(literal) for literal in literals),
                )
            )
            continue
        constraints = tuple(
            _constraint(literal, modes[literal.mode_id], max_variables)
            for literal in literals
        )
        component_variables = set().union(
            *(constraint.variables for constraint in constraints)
        )
        if not component_variables & external:
            replacements.append(
                (
                    "raw",
                    tuple(_literal_key(literal) for literal in literals),
                )
            )
            continue
        normalized = _normalize_component(
            constraints,
            frozenset(component_variables - external),
            max_variables,
        )
        if normalized is None:
            return None
        if any(constraint.variables - safe for constraint in normalized):
            replacements.append(
                (
                    "raw",
                    tuple(_literal_key(literal) for literal in literals),
                )
            )
            continue
        replacements.append(("linear", normalized))

    non_builtin = tuple(
        _literal_key(literal)
        for literal in clause.body
        if modes[literal.mode_id].kind not in {"arithmetic", "comparison"}
    )
    return (
        tuple(_literal_key(literal) for literal in clause.head),
        non_builtin,
        tuple(sorted(replacements, key=repr)),
    )


def _raw_clause_key(clause: ReifiedClause) -> LinearClauseKey:
    return (
        tuple(_literal_key(literal) for literal in clause.head),
        tuple(_literal_key(literal) for literal in clause.body),
    )


def _literal_key(literal: ReifiedLiteral) -> tuple[int, tuple[int, ...]]:
    return literal.mode_id, literal.variables


def _is_linear(mode: HypothesisMode) -> bool:
    return (mode.kind == "arithmetic" and mode.operator in {"+", "-"}) or (
        mode.kind == "comparison" and mode.operator in {"<", "<=", ">", ">=", "!="}
    )


def _constraint(
    literal: ReifiedLiteral,
    mode: HypothesisMode,
    width: int,
) -> LinearConstraint:
    coefficients = [Fraction(0) for _ in range(width)]
    if mode.kind == "arithmetic":
        left, right, result = literal.variables
        coefficients[left] += 1
        coefficients[right] += 1 if mode.operator == "+" else -1
        coefficients[result] -= 1
        return LinearConstraint(tuple(coefficients), "eq")

    left, right = literal.variables
    operator = mode.operator
    if operator in {">", ">="}:
        left, right = right, left
        operator = "<" if operator == ">" else "<="
    coefficients[left] += 1
    coefficients[right] -= 1
    relation = {"<": "lt", "<=": "le", "!=": "ne"}[operator]
    return LinearConstraint(tuple(coefficients), relation)


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
    comparisons = [
        constraint for constraint in rows if constraint.relation != "eq"
    ]
    for equation in equations:
        pivot = next(index for index, value in enumerate(equation) if value)
        reduced = []
        for comparison in comparisons:
            factor = comparison.coefficients[pivot] / equation[pivot]
            coefficients = tuple(
                value - factor * equation_value
                for value, equation_value in zip(
                    comparison.coefficients, equation
                )
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
        constraint.coefficients in equalities
        and constraint.relation in {"lt", "ne"}
        for constraint in normalized
    ):
        return None
    normalized = {
        constraint
        for constraint in normalized
        if not (
            constraint.coefficients in equalities and constraint.relation == "le"
        )
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
            (
                row
                for row in range(pivot_row, len(matrix))
                if matrix[row][column]
            ),
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
