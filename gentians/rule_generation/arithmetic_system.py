from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from math import gcd, lcm

from .arithmetic_expression import ArithmeticExpression
from .canonical_arithmetic_clause import CanonicalArithmeticClause
from .comparison_constraint import ComparisonConstraint
from .expression_constraint import ExpressionConstraint
from .hypothesis_mode import HypothesisMode
from .linear_constraint import LinearConstraint
from .reified_clause import ReifiedClause
from .reified_literal import ReifiedLiteral

ArithmeticSystemKey = tuple[object, ...]


SystemRelation = LinearConstraint | ExpressionConstraint | ComparisonConstraint


@dataclass(frozen=True, slots=True)
class ArithmeticSystem:
    relations: tuple[SystemRelation, ...]

    @property
    def key(self) -> ArithmeticSystemKey:
        return tuple(relation.key for relation in self.relations)

    @property
    def variables(self) -> frozenset[int]:
        return frozenset().union(
            *(relation.variables for relation in self.relations)
        )

    def render(self) -> tuple[str, ...]:
        rendered: list[str] = []
        rendered_guard_keys: set[tuple[object, ...]] = set()
        for relation in self.relations:
            value = (
                relation.render()
            )
            if value not in rendered:
                rendered.append(value)
            if not isinstance(relation, ExpressionConstraint):
                continue
            for key, guard in zip(
                relation.guard_keys, relation.rendered_guards, strict=True
            ):
                if key not in rendered_guard_keys:
                    rendered_guard_keys.add(key)
                    rendered.append(guard)
        return tuple(rendered)

    def remap(
        self, variables: dict[int, int], width: int
    ) -> "ArithmeticSystem":
        return ArithmeticSystem(
            tuple(
                relation.remap(variables, width)
                if isinstance(relation, LinearConstraint)
                else relation.remap(variables)
                for relation in self.relations
            )
        )

def canonical_arithmetic_clause(
    clause: ReifiedClause,
    modes: dict[int, HypothesisMode],
    max_variables: int,
) -> CanonicalArithmeticClause | None:
    builtin = [
        literal
        for literal in clause.body
        if modes[literal.mode_id].kind in {"arithmetic", "comparison"}
    ]
    non_builtin = tuple(
        literal
        for literal in clause.body
        if modes[literal.mode_id].kind not in {"arithmetic", "comparison"}
    )
    if not builtin:
        return CanonicalArithmeticClause(clause.head, non_builtin, ())

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
    numeric_variables = _numeric_variables(clause, modes)

    components: dict[int, list[ReifiedLiteral]] = {}
    for literal in builtin:
        components.setdefault(find(literal.variables[0]), []).append(literal)

    systems: list[ArithmeticSystem] = []
    for literals in components.values():
        numeric_component = any(
            modes[literal.mode_id].kind == "arithmetic"
            or modes[literal.mode_id].operator != "!="
            or set(literal.variables) <= numeric_variables
            for literal in literals
        )
        if not numeric_component:
            systems.append(
                ArithmeticSystem(
                    tuple(
                        _arithmetic_relation(literal, modes, safe)
                        for literal in sorted(literals, key=_literal_key)
                    )
                )
            )
            continue
        if any(
            not _is_linear(
                modes[literal.mode_id],
                set(literal.variables) <= numeric_variables,
            )
            for literal in literals
        ):
            system = _expression_system(
                literals, modes, external, safe, numeric_variables
            )
            systems.append(
                system
                if system is not None
                else ArithmeticSystem(
                    tuple(
                        _arithmetic_relation(literal, modes, safe)
                        for literal in sorted(literals, key=_literal_key)
                    )
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
            systems.append(
                ArithmeticSystem(
                    tuple(
                        _arithmetic_relation(literal, modes, safe)
                        for literal in sorted(literals, key=_literal_key)
                    )
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
        oriented = _orient_linear_constraints(normalized, safe)
        if oriented is None:
            systems.append(
                ArithmeticSystem(
                    tuple(
                        _arithmetic_relation(literal, modes, safe)
                        for literal in sorted(literals, key=_literal_key)
                    )
                )
            )
            continue
        if oriented:
            systems.append(ArithmeticSystem(oriented))

    return CanonicalArithmeticClause(
        clause.head,
        non_builtin,
        tuple(sorted(systems, key=lambda system: repr(system.key))),
    )


def _literal_key(literal: ReifiedLiteral) -> tuple[int, tuple[int, ...]]:
    return literal.mode_id, literal.variables


def _numeric_variables(
    clause: ReifiedClause,
    modes: dict[int, HypothesisMode],
) -> set[int]:
    numeric: set[int] = set()
    for literal in (*clause.head, *clause.body):
        mode = modes[literal.mode_id]
        if mode.kind == "arithmetic" or (
            mode.kind == "comparison" and mode.operator != "!="
        ):
            numeric.update(literal.variables)
        if not mode.arg_types:
            continue
        variable_types = (
            mode.arg_types
            if not mode.fixed_arguments
            else tuple(
                arg_type
                for arg_type, fixed in zip(
                    mode.arg_types, mode.fixed_arguments, strict=True
                )
                if fixed is None
            )
        )
        numeric.update(
            variable
            for variable, arg_type in zip(
                literal.variables, variable_types, strict=True
            )
            if arg_type == "numeric"
        )
    return numeric


def _arithmetic_relation(
    literal: ReifiedLiteral,
    modes: dict[int, HypothesisMode],
    safe: set[int],
) -> SystemRelation:
    mode = modes[literal.mode_id]
    if mode.kind == "comparison":
        return ComparisonConstraint(
            literal.variables[0], literal.variables[1], mode.operator
        )
    if mode.arithmetic is None:
        raise ValueError(f"arithmetic mode {mode.id} has no template")
    known = {
        variable: ArithmeticExpression.var(variable)
        for variable in literal.variables
    }
    expression = _mode_expression(literal, mode, known)
    guards = (
        (known[literal.variables[1]],)
        if mode.arithmetic.operator in {"/", "\\"}
        else ()
    )
    output = literal.variables[-1]
    return ExpressionConstraint(
        expression,
        "eq",
        output,
        output in safe,
        guards,
    )


def _expression_system(
    literals: list[ReifiedLiteral],
    modes: dict[int, HypothesisMode],
    external: set[int],
    safe: set[int],
    numeric_variables: set[int],
) -> ArithmeticSystem | None:
    known = {
        variable: ArithmeticExpression.var(variable)
        for variable in safe
    }
    guards: dict[int, tuple[ArithmeticExpression, ...]] = {
        variable: () for variable in safe
    }
    pending = [
        literal
        for literal in literals
        if modes[literal.mode_id].kind == "arithmetic"
    ]
    comparisons = [
        literal
        for literal in literals
        if modes[literal.mode_id].kind == "comparison"
    ]
    constraints: list[SystemRelation] = []
    while pending:
        progress = False
        for literal in pending[:]:
            mode = modes[literal.mode_id]
            if mode.arithmetic is None:
                return None
            input_variables = literal.variables[:-1]
            if any(variable not in known for variable in input_variables):
                continue
            expression = _mode_expression(literal, mode, known)
            inherited = tuple(
                guard
                for variable in input_variables
                for guard in guards.get(variable, ())
            )
            if mode.arithmetic.operator in {"/", "\\"}:
                inherited = (*inherited, known[input_variables[1]])
            inherited = tuple(dict.fromkeys(inherited))
            output = literal.variables[-1]
            if output in external:
                constraints.append(
                    ExpressionConstraint(
                        expression,
                        "eq",
                        output,
                        output in safe,
                        inherited,
                    )
                )
                known[output] = ArithmeticExpression.var(output)
                guards[output] = ()
            elif output in known:
                prior_guards = guards.get(output, ())
                constraints.append(
                    ExpressionConstraint(
                        ArithmeticExpression(
                            "-", (known[output], expression)
                        ),
                        "eq",
                        guards=tuple(
                            dict.fromkeys((*prior_guards, *inherited))
                        ),
                    )
                )
            else:
                known[output] = expression
                guards[output] = inherited
            pending.remove(literal)
            progress = True
        if not progress:
            return None

    for literal in comparisons:
        left, right = literal.variables
        operator = modes[literal.mode_id].operator
        if operator == "!=" and not set(literal.variables) <= numeric_variables:
            constraints.append(_arithmetic_relation(literal, modes, safe))
            continue
        if left not in known or right not in known:
            return None
        if operator in {">", ">="}:
            left, right = right, left
            operator = "<" if operator == ">" else "<="
        expression = ArithmeticExpression(
            "-", (known[left], known[right])
        )
        relation = {"<": "lt", "<=": "le", "!=": "ne"}[operator]
        inherited = tuple(
            dict.fromkeys((*guards.get(left, ()), *guards.get(right, ())))
        )
        constraints.append(
            ExpressionConstraint(expression, relation, guards=inherited)
        )
    if not constraints:
        return None
    return ArithmeticSystem(
        tuple(sorted(constraints, key=lambda relation: repr(relation.key)))
    )


def _mode_expression(
    literal: ReifiedLiteral,
    mode: HypothesisMode,
    known: dict[int, ArithmeticExpression],
) -> ArithmeticExpression:
    arithmetic = mode.arithmetic
    if arithmetic is None:
        raise ValueError(f"arithmetic mode {mode.id} has no template")
    inputs = literal.variables[:-1]
    if arithmetic.linear:
        positive = [
            known[variable]
            for variable, coefficient in zip(inputs, arithmetic.coefficients)
            if coefficient > 0
        ]
        negative = [
            known[variable]
            for variable, coefficient in zip(inputs, arithmetic.coefficients)
            if coefficient < 0
        ]
        expression = _fold_expression("+", positive)
        for value in negative:
            expression = ArithmeticExpression("-", (expression, value))
        return expression
    left, right = (known[variable] for variable in inputs[:2])
    return ArithmeticExpression(arithmetic.operator, (left, right))


def _orient_linear_constraints(
    constraints: tuple[LinearConstraint, ...],
    initially_safe: set[int],
) -> tuple[SystemRelation, ...] | None:
    safe = set(initially_safe)
    pending = list(constraints)
    oriented: list[SystemRelation] = []
    while pending:
        ready = next(
            (
                constraint
                for constraint in pending
                if not (constraint.variables - safe)
            ),
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
                    constraint.coefficients[
                        next(iter(constraint.variables - safe))
                    ]
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
        target.extend(
            ArithmeticExpression.var(variable) for _ in range(abs(scaled))
        )
    expression = (
        _fold_expression("+", positive)
        if positive
        else ArithmeticExpression.const(0)
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


def _is_linear(mode: HypothesisMode, allow_disequality: bool) -> bool:
    return (
        mode.kind == "arithmetic"
        and mode.arithmetic is not None
        and (mode.arithmetic.linear or mode.arithmetic.operator in {"+", "-"})
    ) or (
        mode.kind == "comparison"
        and (
            mode.operator in {"<", "<=", ">", ">="}
            or (allow_disequality and mode.operator == "!=")
        )
    )


def _constraint(
    literal: ReifiedLiteral,
    mode: HypothesisMode,
    width: int,
) -> LinearConstraint:
    coefficients = [Fraction(0) for _ in range(width)]
    if mode.kind == "arithmetic":
        if mode.arithmetic is None:
            raise ValueError(f"arithmetic mode {mode.id} has no template")
        if mode.arithmetic.linear:
            for variable, coefficient in zip(
                literal.variables, mode.arithmetic.coefficients
            ):
                coefficients[variable] += coefficient
            return LinearConstraint(tuple(coefficients), "eq")
        left, right, result = literal.variables
        coefficients[left] += 1
        coefficients[right] += 1 if mode.arithmetic.operator == "+" else -1
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
