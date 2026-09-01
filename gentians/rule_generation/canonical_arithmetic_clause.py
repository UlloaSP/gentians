from dataclasses import dataclass
from typing import TYPE_CHECKING

from .hypothesis_mode import HypothesisMode
from .reified_clause import _render_literal
from .reified_literal import ReifiedLiteral

if TYPE_CHECKING:
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

    def render(self, modes: dict[int, HypothesisMode]) -> str:
        head = ";".join(
            _render_literal(literal, modes[literal.mode_id])
            for literal in self.head
        )
        body = [
            _render_literal(literal, modes[literal.mode_id])
            for literal in self.body
        ]
        for system in self.systems:
            body.extend(system.render())
        rendered_body = ",".join(body)
        return f"{head} :- {rendered_body}." if head else f":- {rendered_body}."
