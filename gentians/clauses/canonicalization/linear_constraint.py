from dataclasses import dataclass, field

from clingo import ast

from ...language.ast_nodes import binding_term, comparison, operation


@dataclass(frozen=True, slots=True)
class LinearConstraint:
    coefficients: tuple[int, ...]
    relation: str
    _variables: frozenset[int] | None = field(default=None, init=False, repr=False, compare=False)

    @property
    def variables(self) -> frozenset[int]:
        variables = self._variables
        if variables is None:
            variables = frozenset(index for index, coefficient in enumerate(self.coefficients) if coefficient)
            object.__setattr__(self, "_variables", variables)
        return variables

    @property
    def key(self) -> tuple[object, ...]:
        return self.relation, self.coefficients

    def instantiate(self) -> ast.AST:
        expression: ast.AST | None = None
        for variable, coefficient in enumerate(self.coefficients):
            if not coefficient:
                continue
            term = binding_term(f"V{variable}")
            if abs(coefficient) != 1:
                term = operation("*", [binding_term(str(abs(coefficient))), term])
            if expression is None:
                expression = term if coefficient > 0 else operation("neg", [term])
            else:
                expression = operation("+" if coefficient > 0 else "-", [expression, term])
        if expression is None:
            raise ValueError("a linear constraint requires a nonzero coefficient")
        operator = {"eq": "=", "lt": "<", "le": "<=", "ne": "!="}[self.relation]
        return comparison([expression, binding_term("0")], (operator,))

    def render(self) -> str:
        return str(self.instantiate())

    def remap(
        self, variables: dict[int, int], width: int
    ) -> "LinearConstraint":
        coefficients = [0 for _ in range(width)]
        for variable, coefficient in enumerate(self.coefficients):
            if coefficient and variable in variables:
                coefficients[variables[variable]] += coefficient
        return LinearConstraint(tuple(coefficients), self.relation)
