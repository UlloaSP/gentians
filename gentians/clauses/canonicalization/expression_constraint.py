from dataclasses import dataclass
from typing import cast

from clingo import ast

from ...language.ast_nodes import binding_term, comparison, operation
from .expression import ArithmeticExpression


@dataclass(frozen=True, slots=True)
class ExpressionConstraint:
    expression: ArithmeticExpression
    relation: str
    output: int | None = None
    output_is_safe: bool = True
    guards: tuple[ArithmeticExpression, ...] = ()

    @property
    def variables(self) -> frozenset[int]:
        variables = set(self.expression.variables)
        if self.output is not None:
            variables.add(self.output)
        for guard in self.guards:
            variables.update(guard.variables)
        return frozenset(variables)

    @property
    def guard_keys(self) -> tuple[tuple[object, ...], ...]:
        return tuple(guard.key for guard in self._ordered_guards)

    @property
    def _ordered_guards(self) -> tuple[ArithmeticExpression, ...]:
        return tuple(sorted(self.guards, key=lambda guard: repr(guard.key)))

    @property
    def key(self) -> tuple[object, ...]:
        expression_key = self.expression.key
        if (
            self.output is None
            and self.relation in {"eq", "ne"}
            and expression_key[0] == "sum"
        ):
            terms = cast(
                tuple[tuple[tuple[object, ...], int], ...],
                expression_key[1],
            )
            negated = (
                "sum",
                tuple(
                    (term, -coefficient)
                    for term, coefficient in terms
                ),
            )
            expression_key = min(expression_key, negated, key=repr)
        return (
            "expression",
            expression_key,
            self.relation,
            self.output,
            self.guard_keys,
        )

    def instantiate(self) -> ast.AST:
        expression = self.expression.instantiate()
        right = binding_term("0")
        if self.output is not None:
            output = binding_term(f"V{self.output}")
            if self.output_is_safe:
                expression = operation("-", [expression, output])
            else:
                right = output
            operator = "="
        else:
            operator = {"eq": "=", "lt": "<", "le": "<=", "ne": "!="}[self.relation]
        return comparison([expression, right], (operator,))

    def render(self) -> str:
        return str(self.instantiate())

    @property
    def guard_literals(self) -> tuple[ast.AST, ...]:
        return tuple(comparison([guard.instantiate(), binding_term("0")], ("!=",)) for guard in self._ordered_guards)

    @property
    def rendered_guards(self) -> tuple[str, ...]:
        return tuple(str(guard) for guard in self.guard_literals)

    def remap(self, variables: dict[int, int]) -> "ExpressionConstraint":
        return ExpressionConstraint(
            self.expression.remap(variables),
            self.relation,
            None if self.output is None else variables[self.output],
            self.output_is_safe,
            tuple(guard.remap(variables) for guard in self.guards),
        )
