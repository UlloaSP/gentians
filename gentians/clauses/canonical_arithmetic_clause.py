from dataclasses import dataclass
from typing import TYPE_CHECKING

from .hypothesis_mode import HypothesisMode
from ..language.ir.conditional_literal import ConditionalLiteral
from .reified_clause import _render_literal, render_head
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
        head = render_head(self.head, modes)
        body = [
            _render_literal(literal, modes[literal.mode_id])
            for literal in self.body
        ]
        for system in self.systems:
            body.extend(system.render())
        separator = (
            ";"
            if any(
                isinstance(modes[literal.mode_id].literal, ConditionalLiteral)
                for literal in self.body
            )
            else ","
        )
        rendered_body = separator.join(body)
        if not rendered_body:
            if not head:
                raise ValueError("a learned clause cannot have an empty head and body")
            return f"{head}."
        return f"{head} :- {rendered_body}." if head else f":- {rendered_body}."
