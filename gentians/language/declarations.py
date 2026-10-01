import re

from clingo import ast

from .asp import _diagnostic_detail, split_top_level_args
from .grammar import SourceError, _directive_args, _parse_recall, _strip_outer_braces, source_position
from .ir.atom_template import AtomTemplate
from .modes import _get_mode_atom
from .terms import fixed, validate_type


def _get_limit(s: str, name: str, allow_zero: bool) -> int | None:
    raw = _directive_args(s, name).strip()
    if raw == "*":
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"invalid {name} declaration: {s}") from exc
    if value < (0 if allow_zero else 1):
        raise ValueError(f"invalid {name} declaration: {s}")
    return value


def _get_pos_neg_examples(s: str) -> tuple[tuple[str, int, int], ...]:
    name = "#pos" if s.startswith("#pos") else "#neg"
    parts = split_top_level_args(_directive_args(s, name))
    if len(parts) not in (2, 3):
        raise ValueError(f"invalid example declaration: {s}")
    fields = []
    cursor = len(name) + 1
    for part in parts:
        value = _strip_outer_braces(part)
        start = s.index(part, cursor)
        interior = part[1:-1]
        offset = start + 1 + len(interior) - len(interior.lstrip())
        line, column = source_position(s, offset)
        fields.append((value, line, column))
        cursor = start + len(part)
    return tuple(fields)


def _get_invented_declaration(s: str) -> tuple[int, AtomTemplate]:
    parts = split_top_level_args(_directive_args(s, "#invent"))
    if len(parts) != 2:
        raise ValueError(f"invalid #invent declaration: {s}")
    recall = _parse_recall(parts[0])
    offset = s.index(",", len("#invent(")) + 1
    atom = _get_mode_atom(s[offset:-2], s, offset)
    if recall < 1:
        raise ValueError(f"invalid #invent declaration: {s}")
    return recall, atom


def _get_constant_declaration(s: str) -> tuple[str, ast.AST]:
    parts = split_top_level_args(_directive_args(s, "#constant"))
    if len(parts) != 2:
        raise ValueError(f"invalid #constant declaration: {s}")
    type_name = parts[0].strip()
    validate_type(type_name, s)
    try:
        value = fixed(parts[1].strip())
    except RuntimeError as exc:
        detail = str(exc)
        match = re.search(r"(?m)^<string>:(\d+):(\d+)", detail)
        offset = s.index(parts[1], s.index(",") + 1)
        line, column = source_position(s, offset)
        if match:
            column = int(match[2]) + (column - 1 if match[1] == "1" else 0)
            line += int(match[1]) - 1
        raise SourceError(line, f"#constant value must be a ground term: {s}: {_diagnostic_detail(detail)}", column=column) from None
    return type_name, value
