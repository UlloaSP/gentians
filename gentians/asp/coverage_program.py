from pathlib import Path

from clingo import ast

from ..language.asp import AspProgram, parse_program
from ..language.ir.example import Example
from .coverage import generate_clauses_for_coverage_interpretations, guard_context
from .coverage_symbols import ACTIVE_CONTEXT_PREDICATE

COVERAGE_PROGRAM = parse_program(
    (Path(__file__).with_name("rules") / "coverage.lp").read_text()
)


def build_coverage_static_program(
    interpretation_pos: list[Example],
    interpretation_neg: list[Example],
) -> AspProgram:
    statements: list[ast.AST] = []
    context_ids = _context_ids(interpretation_pos, interpretation_neg)
    if context_ids is not None:
        statements.extend(
            parse_program(
                f"1 {{ {ACTIVE_CONTEXT_PREDICATE}(0..{len(context_ids) - 1}) }} 1."
            )
        )
        contexts = {
            example.context_text: example.context
            for example in [*interpretation_pos, *interpretation_neg]
            if example.context
        }
        for text, context in contexts.items():
            statements.extend(guard_context(context, context_ids[text]))
    if interpretation_pos:
        statements.extend(
            parse_program(
                f"pos_exs(0..{len(interpretation_pos) - 1}).\n"
                + generate_clauses_for_coverage_interpretations(
                    interpretation_pos, True, context_ids
                )
            )
        )
    if interpretation_neg:
        statements.extend(
            parse_program(
                f"neg_exs(0..{len(interpretation_neg) - 1}).\n"
                + generate_clauses_for_coverage_interpretations(
                    interpretation_neg, False, context_ids
                )
            )
        )
    statements.extend(COVERAGE_PROGRAM)
    return tuple(statements)


def _context_ids(
    interpretation_pos: list[Example],
    interpretation_neg: list[Example],
) -> dict[str, int] | None:
    examples = [*interpretation_pos, *interpretation_neg]
    if not any(example.context for example in examples):
        return None
    contexts = dict.fromkeys(example.context_text for example in examples)
    return {context: index for index, context in enumerate(contexts)}
