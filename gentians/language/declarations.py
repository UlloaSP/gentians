import re

from clingo import ast

from .asp import _diagnostic_detail, split_top_level_args
from .grammar import SourceError, _directive_args, _parse_integer, _parse_recall, _strip_outer_braces, source_position
from .ir.atom_template import AtomTemplate
from .modes import _get_mode_atom
from .terms import fixed, validate_labels, validate_type


def _get_limit(s: str, name: str, allow_zero: bool) -> int | None:
    raw = _directive_args(s, name).strip()
    if raw == "*":
        return None
    try:
        value = _parse_integer(raw)
    except ValueError as exc:
        raise ValueError(f"invalid {name} declaration: {s}") from exc
    if value < (0 if allow_zero else 1):
        raise ValueError(f"invalid {name} declaration: {s}")
    return value


def _get_pos_neg_examples(s: str) -> tuple[tuple[str, int, int], ...]:
    name = "#pos" if s.startswith("#pos") else "#neg"
    payload = _directive_args(s, name)
    parts = split_top_level_args(payload)
    if len(parts) not in (2, 3):
        raise ValueError(f"invalid example declaration: {s}")
    fields = []
    for start, end in parts:
        part = payload[start:end]
        value = _strip_outer_braces(part)
        interior = part[1:-1]
        offset = len(name) + 1 + start + 1 + len(interior) - len(interior.lstrip())
        line, column = source_position(s, offset)
        fields.append((value, line, column))
    return tuple(fields)


def _get_invented_declaration(s: str) -> tuple[int, AtomTemplate]:
    payload = _directive_args(s, "#invent")
    parts = split_top_level_args(payload)
    if len(parts) != 2:
        raise ValueError(f"invalid #invent declaration: {s}")
    recall = _parse_recall(payload[slice(*parts[0])])
    offset = len("#invent(") + parts[1][0]
    atom = _get_mode_atom(payload[slice(*parts[1])], s, offset)
    try:
        validate_labels(atom.binding_terms, "head")
    except SourceError as error:
        line, column = source_position(s, offset)
        raise error.with_origin(line, column - 3) from None
    return recall, atom


def _get_constant_declaration(s: str) -> tuple[str, ast.AST]:
    payload = _directive_args(s, "#constant")
    parts = split_top_level_args(payload)
    if len(parts) != 2:
        raise ValueError(f"invalid #constant declaration: {s}")
    type_name = payload[slice(*parts[0])]
    try:
        validate_type(type_name, s)
    except ValueError as error:
        line, column = source_position(s, len("#constant(") + parts[0][0])
        raise SourceError(line, str(error), column=column) from None
    try:
        value = fixed(payload[slice(*parts[1])])
    except RuntimeError as exc:
        detail = str(exc)
        match = re.search(r"(?m)^<string>:(\d+):(\d+)", detail)
        offset = len("#constant(") + parts[1][0]
        line, column = source_position(s, offset)
        if match:
            column = int(match[2]) + (column - 1 if match[1] == "1" else 0)
            line += int(match[1]) - 1
        raise SourceError(line, f"#constant value must be a ground term: {s}: {_diagnostic_detail(detail)}", column=column) from None
    return type_name, value
