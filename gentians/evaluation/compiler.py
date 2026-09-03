from functools import lru_cache
from pathlib import Path

from clingo import ast

from ..language.asp import AspProgram, parse_program, parse_rule
from ..language.ir.example import Example

ACTIVE_CONTEXT_PREDICATE = "gentians_internal_active_context"
COVERAGE_PROGRAM = parse_program(
    (Path(__file__).with_name("rules") / "coverage.lp").read_text(encoding="utf-8")
)


def compile_coverage_program(
    positive_examples: list[Example],
    negative_examples: list[Example],
) -> AspProgram:
    statements: list[ast.AST] = []
    context_ids = _context_ids(positive_examples, negative_examples)
    if context_ids is not None:
        statements.extend(
            parse_program(
                f"1 {{ {ACTIVE_CONTEXT_PREDICATE}(0..{len(context_ids) - 1}) }} 1."
            )
        )
        contexts = {
            example.context_text: example.context
            for example in [*positive_examples, *negative_examples]
            if example.context
        }
        for text, context in contexts.items():
            statements.extend(_guard_context(context, context_ids[text]))
    if positive_examples:
        statements.extend(
            parse_program(
                f"pos_exs(0..{len(positive_examples) - 1}).\n"
                + _compile_examples(positive_examples, True, context_ids)
            )
        )
    if negative_examples:
        statements.extend(
            parse_program(
                f"neg_exs(0..{len(negative_examples) - 1}).\n"
                + _compile_examples(negative_examples, False, context_ids)
            )
        )
    statements.extend(COVERAGE_PROGRAM)
    return tuple(statements)


def _compile_examples(
    examples: list[Example],
    positive: bool,
    context_ids: dict[str, int] | None,
) -> str:
    parts: list[str] = []
    suffix = "cp" if positive else "cn"
    for index, example in enumerate(examples):
        guard = (
            f"{ACTIVE_CONTEXT_PREDICATE}({context_ids[example.context_text]})"
            if context_ids is not None
            else ""
        )
        if example.included:
            body = (
                f"{example.included_text}, {guard}" if guard else example.included_text
            )
            parts.append(f"{suffix}i({index}):- {body}.")
        else:
            parts.append(
                f"{suffix}i({index}):- {guard}." if guard else f"{suffix}i({index})."
            )
        for literal in example.excluded:
            atom = str(literal)
            body = f"{atom}, {guard}" if guard else atom
            parts.append(f"{suffix}e({index}):- {body}.")
    return "\n".join(parts) + "\n\n"


def _context_ids(
    positive_examples: list[Example],
    negative_examples: list[Example],
) -> dict[str, int] | None:
    examples = [*positive_examples, *negative_examples]
    if not any(example.context for example in examples):
        return None
    contexts = dict.fromkeys(example.context_text for example in examples)
    return {context: index for index, context in enumerate(contexts)}


def _guard_context(context: AspProgram, context_id: int) -> AspProgram:
    guard = _context_guard(context_id)
    return tuple(
        statement.update(body=[*statement.body, guard]) for statement in context
    )


@lru_cache(maxsize=None)
def _context_guard(context_id: int) -> ast.AST:
    return parse_rule(f":- {ACTIVE_CONTEXT_PREDICATE}({context_id}).").body[0]
