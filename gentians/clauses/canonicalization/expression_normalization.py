from collections.abc import Set
from heapq import heapify, heappop, heappush

from ..arithmetic_literal import ArithmeticLiteral
from ...language.ir.comparison_literal import ComparisonLiteral
from ..clause_mode import ClauseMode
from ..reified_literal import ReifiedLiteral
from .arithmetic_system import ArithmeticSystem, SystemRelation
from .comparison_constraint import ComparisonConstraint
from .expression import ArithmeticExpression
from .expression_constraint import ExpressionConstraint
from .term_comparison_constraint import TermComparisonConstraint


def _arithmetic_relation(
    literal: ReifiedLiteral,
    modes: dict[int, ClauseMode],
    safe: Set[int],
) -> SystemRelation:
    mode = modes[literal.mode_id]
    if isinstance(mode.literal, ComparisonLiteral):
        if not mode.literal.simple or mode.literal.arithmetic:
            return _term_comparison(literal, mode)
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
    literal: ReifiedLiteral, mode: ClauseMode
) -> TermComparisonConstraint:
    if not isinstance(mode.literal, ComparisonLiteral):
        raise ValueError("comparison mode has no comparison template")
    variables = iter(literal.variables)
    terms: list[ArithmeticExpression] = []
    for steps in mode.comparison_steps:
        results: list[ArithmeticExpression] = []
        for kind, value, count in steps:
            children = tuple(results[-count:]) if count else ()
            if count:
                del results[-count:]
            if kind == "variable":
                result = ArithmeticExpression.var(next(variables))
            elif kind == "number":
                assert isinstance(value, int)
                result = ArithmeticExpression.const(value)
            elif kind == "fixed":
                assert isinstance(value, str)
                result = ArithmeticExpression.fixed(value)
            elif kind == "constant":
                raise ValueError("constant placeholder was not concretized")
            else:
                assert isinstance(value, str)
                result = ArithmeticExpression(value, children)
            results.append(result)
        terms.append(results[0])
    try:
        next(variables)
    except StopIteration:
        return TermComparisonConstraint(tuple(terms), mode.literal.operators)
    raise ValueError("comparison has more assigned variables than bindings")


def _expression_system(
    literals: list[ReifiedLiteral],
    modes: dict[int, ClauseMode],
    external: Set[int],
    safe: Set[int],
    numeric_variables: Set[int],
) -> ArithmeticSystem | None:
    known = {variable: ArithmeticExpression.var(variable) for variable in safe}
    guards: dict[int, tuple[ArithmeticExpression, ...]] = {
        variable: () for variable in safe
    }
    assignments = [
        (literal, modes[literal.mode_id])
        for literal in literals
        if isinstance(modes[literal.mode_id].literal, ArithmeticLiteral)
    ]
    comparisons = [
        literal
        for literal in literals
        if isinstance(modes[literal.mode_id].literal, ComparisonLiteral)
    ]
    constraints: list[SystemRelation] = []
    waiting: dict[int, list[int]] = {}
    missing_counts: list[int] = []
    ready: list[tuple[int, int]] = []
    for index, (literal, _mode) in enumerate(assignments):
        missing = set(literal.variables[:-1]) - known.keys()
        missing_counts.append(len(missing))
        if not missing:
            ready.append((0, index))
        for variable in missing:
            waiting.setdefault(variable, []).append(index)
    heapify(ready)
    resolved = 0
    while ready:
        scan, index = heappop(ready)
        literal, mode = assignments[index]
        if not isinstance(mode.literal, ArithmeticLiteral):
            return None
        input_variables = literal.variables[:-1]
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
        newly_known = output not in known
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
        if newly_known:
            for consumer in waiting.pop(output, ()):
                missing_counts[consumer] -= 1
                if not missing_counts[consumer]:
                    # Match left-to-right scans: an earlier slot waits for the
                    # next scan, so repeated outputs retain their prior order.
                    heappush(ready, (scan + (consumer <= index), consumer))
        resolved += 1
    if resolved != len(assignments):
        return None

    for literal in comparisons:
        mode = modes[literal.mode_id]
        comparison = mode.literal
        if not isinstance(comparison, ComparisonLiteral):
            return None
        if not comparison.simple or comparison.arithmetic:
            constraints.append(_term_comparison(literal, mode))
            continue
        left, right = literal.variables
        operator = comparison.operators[0]
        if operator == "=":
            constraints.append(_term_comparison(literal, mode))
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

    results: list[ArithmeticExpression] = []
    for operator, count in mode.arithmetic_steps:
        if not operator:
            result = known[next(variables)]
        elif operator == "unsupported":
            raise ValueError("unsupported arithmetic term in compiled mode")
        else:
            children = tuple(results[-count:]) if count else ()
            if count:
                del results[-count:]
            result = ArithmeticExpression(operator, children)
        results.append(result)
    return results[0]
