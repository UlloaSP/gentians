from dataclasses import dataclass
from functools import lru_cache

from clingo import ast

from ..language import terms as mode_terms
from ..language.ast_nodes import literal
from ..language.ir.literal_template import instantiate_literal
from .clause_mode import ClauseMode
from .reified_literal import ReifiedLiteral


@dataclass(frozen=True, slots=True)
class ReifiedClause:
    head: tuple[ReifiedLiteral, ...]
    body: tuple[ReifiedLiteral, ...]


@lru_cache(maxsize=8192)
def _instantiate_literal(literal: ReifiedLiteral, mode: ClauseMode) -> ast.AST:
    return instantiate_literal(mode.literal, literal.variables)


def instantiate_head(
    head: tuple[ReifiedLiteral, ...], modes: dict[int, ClauseMode]
) -> ast.AST:
    if not head:
        return literal(ast.BooleanConstant(False))
    head_modes = tuple(modes[literal.mode_id] for literal in head)
    form = head_modes[0].head_form
    if form is None or any(mode.head_form != form for mode in head_modes):
        raise ValueError("clause head does not belong to one complete #modeh form")
    atoms = tuple(
        _instantiate_literal(
            ReifiedLiteral(
                literal.section, literal.slot, literal.mode_id,
                literal.variables[:sum(len(mode_terms.bindings(term)) for term in mode.literal.arguments)],
            ),
            mode,
        )
        for literal, mode in zip(head, head_modes, strict=True)
    )
    template = head_modes[0].head
    if template is None or any(mode.head != template for mode in head_modes):
        raise ValueError("clause head does not share one complete #modeh template")
    first_count = sum(len(mode_terms.bindings(term)) for term in head_modes[0].literal.arguments)
    guard_variables = tuple(f"V{variable}" for variable in head[0].variables[first_count:])
    return template.instantiate(atoms, guard_variables)
