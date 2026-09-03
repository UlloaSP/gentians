from dataclasses import dataclass

from .clause_mode import ClauseMode
from ..language.ir.literal_template import render_literal
from .reified_literal import ReifiedLiteral


@dataclass(frozen=True, slots=True)
class ReifiedClause:
    head: tuple[ReifiedLiteral, ...]
    body: tuple[ReifiedLiteral, ...]


def _render_literal(literal: ReifiedLiteral, mode: ClauseMode) -> str:
    return render_literal(mode.literal, literal.variables)


def render_head(
    head: tuple[ReifiedLiteral, ...], modes: dict[int, ClauseMode]
) -> str:
    if not head:
        return ""
    head_modes = tuple(modes[literal.mode_id] for literal in head)
    form = head_modes[0].head_form
    if form is None or any(mode.head_form != form for mode in head_modes):
        raise ValueError("clause head does not belong to one complete #modeh form")
    atoms = tuple(
        _render_literal(literal, mode)
        for literal, mode in zip(head, head_modes, strict=True)
    )
    template = head_modes[0].head
    if template is None or any(mode.head != template for mode in head_modes):
        raise ValueError("clause head does not share one complete #modeh template")
    return template.render(atoms)
