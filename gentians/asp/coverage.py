from clingo import ast

from ..rule_generation.example import Example
from ..rule_generation.parser import split_top_level_args
from .coverage_symbols import ACTIVE_CONTEXT_PREDICATE


class Coverage:
    __slots__ = ("neg_mask", "pos_mask")

    def __init__(self, l_pos: list[int], l_neg: list[int]):
        self.pos_mask = _mask(l_pos)
        self.neg_mask = _mask(l_neg)

    def extend(self, l_pos: list[int], l_neg: list[int]) -> None:
        self.pos_mask |= _mask(l_pos)
        self.neg_mask |= _mask(l_neg)

    def extend_masks(self, pos_mask: int, neg_mask: int) -> None:
        self.pos_mask |= pos_mask
        self.neg_mask |= neg_mask


def _mask(values: list[int]) -> int:
    mask = 0
    for value in values:
        mask |= 1 << value
    return mask


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
            f"{ACTIVE_CONTEXT_PREDICATE}({context_ids[example.context]})"
            if context_ids is not None
            else ""
        )
        if len(example.included) > 0:
            body = f"{example.included}, {guard}" if guard else example.included
            parts.append(f"{suffix}i({cl_index}):- {body}.")
        else:
            parts.append(
                f"{suffix}i({cl_index}):- {guard}."
                if guard
                else f"{suffix}i({cl_index})."
            )

        if len(example.excluded) > 0:
            for atom in split_top_level_args(example.excluded):
                body = f"{atom}, {guard}" if guard else atom
                parts.append(f"{suffix}e({cl_index}):- {body}.")

    return "\n".join(parts) + "\n\n"


def guard_context(context: str, context_id: int) -> str:
    """Add an active-context condition to every contextual ASP statement."""
    statements: list[ast.AST] = []
    source = context if context.rstrip().endswith((".", "]")) else f"{context}."
    ast.parse_string(source, statements.append)

    guard_statements: list[ast.AST] = []
    ast.parse_string(
        f":- {ACTIVE_CONTEXT_PREDICATE}({context_id}).",
        guard_statements.append,
    )
    guard = next(
        statement.body[0]
        for statement in guard_statements
        if statement.ast_type == ast.ASTType.Rule
    )

    guarded: list[str] = []
    seen_program = False
    for statement in statements:
        if statement.ast_type == ast.ASTType.Program:
            if seen_program:
                raise ValueError(
                    f"unsupported statement in example context: {statement.ast_type}"
                )
            seen_program = True
            continue
        if statement.ast_type != ast.ASTType.Rule:
            raise ValueError(
                f"unsupported statement in example context: {statement.ast_type}"
            )
        guarded.append(str(statement.update(body=[*statement.body, guard])))
    return "\n".join(guarded)
