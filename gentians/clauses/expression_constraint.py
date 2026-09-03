from dataclasses import dataclass
from typing import cast

from .arithmetic_expression import ArithmeticExpression


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

    def render(self) -> str:
        expression = self.expression.render()
        if self.output is not None:
            if self.output_is_safe:
                expression = f"{expression}-V{self.output}"
                rendered = f"{expression}=0"
            else:
                rendered = f"{expression}=V{self.output}"
        else:
            operator = {"eq": "=", "lt": "<", "le": "<=", "ne": "!="}[
                self.relation
            ]
            rendered = f"{expression}{operator}0"
        return rendered

    @property
    def rendered_guards(self) -> tuple[str, ...]:
        return tuple(f"{guard.render()}!=0" for guard in self._ordered_guards)

    def remap(self, variables: dict[int, int]) -> "ExpressionConstraint":
        return ExpressionConstraint(
            self.expression.remap(variables),
            self.relation,
            None if self.output is None else variables[self.output],
            self.output_is_safe,
            tuple(guard.remap(variables) for guard in self.guards),
        )
