from dataclasses import dataclass
from functools import lru_cache

from clingo import ast

from ..language.ast_nodes import binding_terms, consume_all, literal
from ..language.ir.literal_template import LiteralTemplate
from .arithmetic_literal import ArithmeticLiteral
from .clause_mode import ClauseMode
from .reified_literal import ReifiedLiteral


@dataclass(frozen=True, slots=True)
class ReifiedClause:
    head: tuple[ReifiedLiteral, ...]
    body: tuple[ReifiedLiteral, ...]


def instantiate_literal(
    template: LiteralTemplate | ArithmeticLiteral, variables: tuple[int, ...]
) -> ast.AST:
    bindings = binding_terms(f"V{variable}" for variable in variables)
    node = template.instantiate(bindings)
    consume_all(bindings)
    return node


@lru_cache(maxsize=8192)
def _instantiate_literal(mode: ClauseMode, variables: tuple[int, ...]) -> ast.AST:
    return instantiate_literal(mode.literal, variables)


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
            mode,
            literal.variables[:mode.literal_binding_count],
        )
        for literal, mode in zip(head, head_modes, strict=True)
    )
    template = head_modes[0].head
    if template is None or any(mode.head != template for mode in head_modes):
        raise ValueError("clause head does not share one complete #modeh template")
    first_count = head_modes[0].literal_binding_count
    guard_variables = tuple(f"V{variable}" for variable in head[0].variables[first_count:])
    return template.instantiate(atoms, guard_variables)
