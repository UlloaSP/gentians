from dataclasses import dataclass

from clingo import ast

from ...language.ast_nodes import binding_term, comparison


@dataclass(frozen=True, slots=True)
class ComparisonConstraint:
    left: int
    right: int
    operator: str

    @property
    def variables(self) -> frozenset[int]:
        return frozenset((self.left, self.right))

    @property
    def key(self) -> tuple[object, ...]:
        variables = (self.left, self.right)
        if self.operator in {"=", "!="}:
            variables = tuple(sorted(variables))
        return "comparison", self.operator, variables

    def instantiate(self) -> ast.AST:
        return comparison([binding_term(f"V{self.left}"), binding_term(f"V{self.right}")], (self.operator,))

    def render(self) -> str:
        return str(self.instantiate())

    def remap(self, variables: dict[int, int]) -> "ComparisonConstraint":
        return ComparisonConstraint(
            variables[self.left], variables[self.right], self.operator
        )
