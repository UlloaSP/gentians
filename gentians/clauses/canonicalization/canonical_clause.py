from dataclasses import dataclass

from clingo import ast

from ...language.ast_nodes import LOCATION
from ..clause_mode import ClauseMode
from ..reified_clause import _instantiate_literal, instantiate_head
from ..reified_literal import ReifiedLiteral
from .arithmetic_system import ArithmeticSystem, ArithmeticSystemKey


@dataclass(frozen=True, slots=True)
class CanonicalArithmeticClause:
    head: tuple[ReifiedLiteral, ...]
    body: tuple[ReifiedLiteral, ...]
    systems: tuple["ArithmeticSystem", ...]

    @property
    def key(self) -> "ArithmeticSystemKey":
        return (
            tuple((literal.mode_id, literal.variables) for literal in self.head),
            tuple((literal.mode_id, literal.variables) for literal in self.body),
            tuple(system.key for system in self.systems),
        )

    def instantiate(
        self,
        modes: dict[int, ClauseMode],
        heads: dict[tuple[ReifiedLiteral, ...], ast.AST] | None = None,
    ) -> ast.AST:
        """Build the rule once; the evaluator consumes this same AST."""
        if not self.head and not self.body and not self.systems:
            raise ValueError("a learned clause cannot have an empty head and body")
        if heads is None:
            head = instantiate_head(self.head, modes)
        else:
            cached = heads.get(self.head)
            if cached is None:
                cached = heads[self.head] = instantiate_head(self.head, modes)
            head = cached
        body = [
            _instantiate_literal(modes[literal.mode_id], literal.variables)
            for literal in self.body
        ]
        for system in self.systems:
            body.extend(system.instantiate())
        return ast.Rule(LOCATION, head, body)

    def render(self, modes: dict[int, ClauseMode]) -> str:
        return str(self.instantiate(modes))
