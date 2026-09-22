from collections.abc import Set

from ...language.ir.arithmetic_literal import ArithmeticLiteral
from ...language.ir.comparison_literal import ComparisonLiteral
from ...language.ir.term_template import TermTemplate
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
    external: Set[int],
    safe: Set[int],
    numeric_variables: Set[int],
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
