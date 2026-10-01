from collections.abc import Set

from clingo import ast

from ...language import terms as mode_terms
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

    def instantiate(term: ast.AST) -> ArithmeticExpression:
        results: list[ArithmeticExpression] = []
        for node, count in mode_terms._postorder(term):
            children = tuple(results[-count:]) if count else ()
            if count:
                del results[-count:]
            kind = mode_terms.kind(node)
            if kind == "variable":
                result = ArithmeticExpression.var(next(variables))
            elif kind == "fixed":
                try:
                    result = ArithmeticExpression.const(int(mode_terms.value(node)))
                except ValueError:
                    result = ArithmeticExpression.fixed(mode_terms.value(node))
            elif kind == "constant":
                raise ValueError("constant placeholder was not concretized")
            else:
                operator = {"function": f"function:{mode_terms.value(node)}", "tuple": "tuple", "interval": "interval"}.get(kind, mode_terms.value(node))
                result = ArithmeticExpression(operator, children)
            results.append(result)
        return results[0]

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

    def instantiate(term: ast.AST) -> ArithmeticExpression:
        if mode_terms.kind(term) == "variable":
            return known[next(variables)]
        if mode_terms.kind(term) != "arithmetic":
            raise ValueError("unsupported arithmetic term in compiled mode")
        return ArithmeticExpression(
            mode_terms.value(term),
            tuple(instantiate(argument) for argument in mode_terms.arguments(term)),
        )

    if mode.literal.operator == "abs":
        return ArithmeticExpression("abs", tuple(instantiate(term) for term in mode.literal.arguments[:-1]))
    return instantiate(mode.literal.expression)
