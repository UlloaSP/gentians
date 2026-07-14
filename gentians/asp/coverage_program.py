from pathlib import Path

from .coverage import generate_clauses_for_coverage_interpretations
from .coverage_symbols import SELECTED_PREDICATE
from ..rule_generation.example import Example


COVERAGE_RULES = (Path(__file__).with_name("rules") / "coverage.lp").read_text()


def build_coverage_static_program(
    background: list[str],
    interpretation_pos: list[Example],
    interpretation_neg: list[Example],
) -> str:
    parts = list(background)
    if interpretation_pos:
        parts.append(f"pos_exs(0..{len(interpretation_pos) - 1}).")
        parts.append(
            generate_clauses_for_coverage_interpretations(interpretation_pos, True)
        )
    if interpretation_neg:
        parts.append(f"neg_exs(0..{len(interpretation_neg) - 1}).")
        parts.append(
            generate_clauses_for_coverage_interpretations(interpretation_neg, False)
        )
    parts.append(COVERAGE_RULES)
    return "\n".join(parts)


def build_fixed_coverage_program(
    background: list[str],
    program: tuple[str, ...],
    interpretation_pos: list[Example],
    interpretation_neg: list[Example],
) -> str:
    static_program = build_coverage_static_program(
        background, interpretation_pos, interpretation_neg
    )
    return static_program + "\n" + "\n".join(program)


def build_subset_coverage_program(
    coverage_static_program: str, program: tuple[str, ...]
) -> str:
    return (
        coverage_static_program
        + "\n"
        + "\n".join(
            clause_with_atom(rule, f"{SELECTED_PREDICATE}({index})")
            for index, rule in enumerate(program)
        )
        + "\n"
        + "\n".join(
            f"{{{SELECTED_PREDICATE}({index})}}."
            for index in range(len(program))
        )
        + f"\n#show {SELECTED_PREDICATE}/1."
    )


def clause_with_atom(clause: str, selected: str) -> str:
    content = clause.strip().rstrip(".")
    if ":-" in content:
        head, body = content.split(":-", 1)
        return f"{head.strip()} :- {body.strip()}, {selected}."
    return f"{content} :- {selected}."
