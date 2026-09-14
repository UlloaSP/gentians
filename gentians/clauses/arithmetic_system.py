from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from math import gcd, lcm

from .arithmetic_expression import ArithmeticExpression
from ..language.ir.arithmetic_literal import ArithmeticLiteral
from ..language.ir.aggregate_literal import AggregateLiteral
from ..language.ir.atom_literal import AtomLiteral
from .canonical_arithmetic_clause import CanonicalArithmeticClause
from .comparison_constraint import ComparisonConstraint
from ..language.ir.comparison_literal import ComparisonLiteral
from .expression_constraint import ExpressionConstraint
from .clause_mode import ClauseMode
from .linear_constraint import LinearConstraint
from .reified_clause import ReifiedClause
from .reified_literal import ReifiedLiteral
from .term_comparison_constraint import TermComparisonConstraint
from ..language.ir.term_template import TermTemplate

ArithmeticSystemKey = tuple[object, ...]


SystemRelation = (
    LinearConstraint
    | ExpressionConstraint
    | ComparisonConstraint
    | TermComparisonConstraint
)


def _is_builtin(mode: ClauseMode) -> bool:
    return isinstance(mode.literal, ArithmeticLiteral) or (
        isinstance(mode.literal, ComparisonLiteral)
        and not mode.literal.default_negated
        and bool(mode.bindings)
        and (
            mode.literal.canonicalizable
            or mode.literal.arithmetic
            or all(binding.type == "numeric" for binding in mode.bindings)
        )
    )


def _is_positive_atom(mode: ClauseMode) -> bool:
    return isinstance(mode.literal, AtomLiteral) and not mode.literal.default_negated


def _is_numeric_builtin(mode: ClauseMode) -> bool:
    return isinstance(mode.literal, ArithmeticLiteral) or (
        isinstance(mode.literal, ComparisonLiteral)
        and (
            mode.literal.arithmetic
            or all(binding.type == "numeric" for binding in mode.bindings)
        )
    )


@dataclass(frozen=True, slots=True)
class ArithmeticSystem:
    relations: tuple[SystemRelation, ...]

    @property
    def key(self) -> ArithmeticSystemKey:
        return tuple(relation.key for relation in self.relations)

    @property
    def variables(self) -> frozenset[int]:
        return frozenset().union(*(relation.variables for relation in self.relations))

    def render(self) -> tuple[str, ...]:
        rendered: list[str] = []
        rendered_guard_keys: set[tuple[object, ...]] = set()
        for relation in self.relations:
            value = relation.render()
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

    def remap(self, variables: dict[int, int], width: int) -> "ArithmeticSystem":
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
    modes: dict[int, ClauseMode],
    max_variables: int,
) -> CanonicalArithmeticClause | None:
    builtin = [
        literal for literal in clause.body if _is_builtin(modes[literal.mode_id])
    ]
    non_builtin = tuple(
        literal for literal in clause.body if not _is_builtin(modes[literal.mode_id])
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
        if not _is_builtin(modes[literal.mode_id])
        for variable in literal.variables
    }
    external.update(
        variable for literal in clause.head for variable in literal.variables
    )
    safe = {
        variable
        for literal in clause.body
        if _is_positive_atom(modes[literal.mode_id])
        for variable in literal.variables
    }
    safe.update(
        literal.variables[-1]
        for literal in clause.body
        if isinstance(modes[literal.mode_id].literal, AggregateLiteral)
    )
    numeric_variables = _numeric_variables(clause, modes)

    components: dict[int, list[ReifiedLiteral]] = {}
    for literal in builtin:
        components.setdefault(find(literal.variables[0]), []).append(literal)

    systems: list[ArithmeticSystem] = []
    for literals in components.values():
        numeric_component = any(
            _is_numeric_builtin(modes[literal.mode_id])
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
    modes: dict[int, ClauseMode],
) -> set[int]:
    numeric: set[int] = set()
    for literal in (*clause.head, *clause.body):
        mode = modes[literal.mode_id]
        if _is_numeric_builtin(mode):
            numeric.update(literal.variables)
        numeric.update(
            variable
            for variable, binding in zip(literal.variables, mode.bindings, strict=True)
            if binding.type == "numeric"
        )
    return numeric


def _arithmetic_relation(
    literal: ReifiedLiteral,
    modes: dict[int, ClauseMode],
    safe: set[int],
) -> SystemRelation:
    mode = modes[literal.mode_id]
    if isinstance(mode.literal, ComparisonLiteral):
        if not mode.literal.simple or mode.literal.arithmetic:
            return _term_comparison(literal, mode.literal)
        return ComparisonConstraint(
            literal.variables[0], literal.variables[1], mode.literal.operators[0]
        )
    if not isinstance(mode.literal, ArithmeticLiteral):
        raise ValueError(f"arithmetic mode {mode.id} has no template")
    known = {
        variable: ArithmeticExpression.var(variable) for variable in literal.variables
    }
    expression = _mode_expression(literal, mode, known)
    guards = (
        (known[literal.variables[1]],) if mode.literal.operator in {"/", "\\"} else ()
    )
    output = literal.variables[-1]
    return ExpressionConstraint(
        expression,
        "eq",
        output,
        output in safe,
        guards,
    )


def _term_comparison(
    literal: ReifiedLiteral, comparison: ComparisonLiteral
) -> TermComparisonConstraint:
    variables = iter(literal.variables)

    def instantiate(term: TermTemplate) -> ArithmeticExpression:
        if term.kind == "variable":
            return ArithmeticExpression.var(next(variables))
        if term.kind == "fixed":
            try:
                return ArithmeticExpression.const(int(term.value))
            except ValueError:
                return ArithmeticExpression.fixed(term.value)
        if term.kind == "constant":
            raise ValueError("constant placeholder was not concretized")
        operator = {
            "function": f"function:{term.value}",
            "tuple": "tuple",
            "interval": "interval",
        }.get(term.kind, term.value)
        return ArithmeticExpression(
            operator,
            tuple(instantiate(argument) for argument in term.arguments),
        )

    terms = tuple(instantiate(term) for term in comparison.terms)
    try:
        next(variables)
    except StopIteration:
        return TermComparisonConstraint(terms, comparison.operators)
    raise ValueError("comparison has more assigned variables than bindings")


def _expression_system(
    literals: list[ReifiedLiteral],
    modes: dict[int, ClauseMode],
    external: set[int],
    safe: set[int],
    numeric_variables: set[int],
) -> ArithmeticSystem | None:
    known = {variable: ArithmeticExpression.var(variable) for variable in safe}
    guards: dict[int, tuple[ArithmeticExpression, ...]] = {
        variable: () for variable in safe
    }
    pending = [
        literal
        for literal in literals
        if isinstance(modes[literal.mode_id].literal, ArithmeticLiteral)
    ]
    comparisons = [
        literal
        for literal in literals
        if isinstance(modes[literal.mode_id].literal, ComparisonLiteral)
    ]
    constraints: list[SystemRelation] = []
    while pending:
        progress = False
        for literal in pending[:]:
            mode = modes[literal.mode_id]
            if not isinstance(mode.literal, ArithmeticLiteral):
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
            if mode.literal.operator in {"/", "\\"}:
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
                        ArithmeticExpression("-", (known[output], expression)),
                        "eq",
                        guards=tuple(dict.fromkeys((*prior_guards, *inherited))),
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
        comparison = modes[literal.mode_id].literal
        if not isinstance(comparison, ComparisonLiteral):
            return None
        if not comparison.simple or comparison.arithmetic:
            constraints.append(_term_comparison(literal, comparison))
            continue
        left, right = literal.variables
        operator = comparison.operators[0]
        if operator == "=":
            constraints.append(_term_comparison(literal, comparison))
            continue
        if operator == "!=" and not set(literal.variables) <= numeric_variables:
            constraints.append(_arithmetic_relation(literal, modes, safe))
            continue
        if left not in known or right not in known:
            return None
        if operator in {">", ">="}:
            left, right = right, left
            operator = "<" if operator == ">" else "<="
        expression = ArithmeticExpression("-", (known[left], known[right]))
        relation = {"<": "lt", "<=": "le", "!=": "ne"}[operator]
        inherited = tuple(
            dict.fromkeys((*guards.get(left, ()), *guards.get(right, ())))
        )
        constraints.append(ExpressionConstraint(expression, relation, guards=inherited))
    if not constraints:
        return None
    return ArithmeticSystem(
        tuple(sorted(constraints, key=lambda relation: repr(relation.key)))
    )


def _mode_expression(
    literal: ReifiedLiteral,
    mode: ClauseMode,
    known: dict[int, ArithmeticExpression],
) -> ArithmeticExpression:
    if not isinstance(mode.literal, ArithmeticLiteral):
        raise ValueError(f"arithmetic mode {mode.id} has no template")
    inputs = literal.variables[:-1]
    variables = iter(inputs)

    def instantiate(term: TermTemplate) -> ArithmeticExpression:
        if term.kind == "variable":
            return known[next(variables)]
        if term.kind != "arithmetic":
            raise ValueError("unsupported arithmetic term in compiled mode")
        return ArithmeticExpression(
            term.value,
            tuple(instantiate(argument) for argument in term.arguments),
        )

    return instantiate(mode.literal.expression)


def _orient_linear_constraints(
    constraints: tuple[LinearConstraint, ...],
    initially_safe: set[int],
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
