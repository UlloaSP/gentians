from dataclasses import dataclass, field
from functools import lru_cache

from clingo import ast

from ...language.ast_nodes import binding_term, comparison, operation


@dataclass(frozen=True, slots=True)
class LinearConstraint:
    coefficients: tuple[int, ...]
    relation: str
    _variable_mask: int | None = field(default=None, init=False, repr=False, compare=False)

    @property
    def variable_mask(self) -> int:
        mask = self._variable_mask
        if mask is None:
            mask = sum(1 << index for index, coefficient in enumerate(self.coefficients) if coefficient)
            object.__setattr__(self, "_variable_mask", mask)
        return mask

    @property
    def variables(self) -> frozenset[int]:
        mask = self.variable_mask
        return frozenset(index for index in range(mask.bit_length()) if mask & (1 << index))

    @property
    def key(self) -> tuple[object, ...]:
        return self.relation, self.coefficients

    @lru_cache(maxsize=8192)
    def instantiate(self) -> ast.AST:
        # Exact coefficient rows have context-free native syntax. Callers use
        # AST.update to construct changes without mutating this shared value.
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
