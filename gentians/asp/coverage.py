from functools import lru_cache

from clingo import ast

from ..language.ir.example import Example
from ..language.asp import AspProgram, parse_rule
from .coverage_symbols import ACTIVE_CONTEXT_PREDICATE


class Coverage:
    __slots__ = ("neg_mask", "pos_mask")

    def __init__(self):
        self.pos_mask = 0
        self.neg_mask = 0

    def extend_masks(self, pos_mask: int, neg_mask: int) -> None:
        self.pos_mask |= pos_mask
        self.neg_mask |= neg_mask


def generate_clauses_for_coverage_interpretations(
    interpretations: list[Example],
    positive: bool,
    context_ids: dict[str, int] | None = None,
) -> str:
    """
    Generates the clauses for the ASP solver to check the coverage.
    TODO: alternative ({a,b},{c,d}) <=> a,b,not c, not d instead
    of two different rules.
    """
    parts: list[str] = []
    suffix: str = "cp" if positive else "cn"
    for cl_index, example in enumerate(interpretations):
        guard = (
            f"{ACTIVE_CONTEXT_PREDICATE}({context_ids[example.context_text]})"
            if context_ids is not None
            else ""
        )
        if example.included:
            body = (
                f"{example.included_text}, {guard}"
                if guard
                else example.included_text
            )
            parts.append(f"{suffix}i({cl_index}):- {body}.")
        else:
            parts.append(
                f"{suffix}i({cl_index}):- {guard}."
                if guard
                else f"{suffix}i({cl_index})."
            )

        if example.excluded:
            for literal in example.excluded:
                atom = str(literal)
                body = f"{atom}, {guard}" if guard else atom
                parts.append(f"{suffix}e({cl_index}):- {body}.")

    return "\n".join(parts) + "\n\n"


def guard_context(context: AspProgram, context_id: int) -> AspProgram:
    """Add an active-context condition to every contextual ASP statement."""
    guard = _context_guard(context_id)
    return tuple(
        statement.update(body=[*statement.body, guard]) for statement in context
    )


@lru_cache(maxsize=None)
def _context_guard(context_id: int) -> ast.AST:
    return parse_rule(f":- {ACTIVE_CONTEXT_PREDICATE}({context_id}).").body[0]
