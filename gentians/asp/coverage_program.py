from pathlib import Path

from ..clauses.example import Example
from .coverage import generate_clauses_for_coverage_interpretations, guard_context
from .coverage_symbols import ACTIVE_CONTEXT_PREDICATE

COVERAGE_RULES = (Path(__file__).with_name("rules") / "coverage.lp").read_text()


def build_coverage_static_program(
    background: list[str],
    interpretation_pos: list[Example],
    interpretation_neg: list[Example],
) -> str:
    parts = list(background)
    context_ids = _context_ids(interpretation_pos, interpretation_neg)
    if context_ids is not None:
        parts.append(
            f"1 {{ {ACTIVE_CONTEXT_PREDICATE}(0..{len(context_ids) - 1}) }} 1."
        )
        parts.extend(
            guard_context(context, context_id)
            for context, context_id in context_ids.items()
            if context
        )
    if interpretation_pos:
        parts.append(f"pos_exs(0..{len(interpretation_pos) - 1}).")
        parts.append(
            generate_clauses_for_coverage_interpretations(
                interpretation_pos, True, context_ids
            )
        )
    if interpretation_neg:
        parts.append(f"neg_exs(0..{len(interpretation_neg) - 1}).")
        parts.append(
            generate_clauses_for_coverage_interpretations(
                interpretation_neg, False, context_ids
            )
        )
    parts.append(COVERAGE_RULES)
    return "\n".join(parts)


def _context_ids(
    interpretation_pos: list[Example],
    interpretation_neg: list[Example],
) -> dict[str, int] | None:
    examples = [*interpretation_pos, *interpretation_neg]
    if not any(example.context for example in examples):
        return None
    contexts = dict.fromkeys(example.context for example in examples)
    return {context: index for index, context in enumerate(contexts)}
