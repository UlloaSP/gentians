import clingo


from .asp import split_top_level_args
from .directives import _directive_args, _parse_recall, _strip_outer_braces
from .ir.atom_template import AtomTemplate
from .modes import _get_mode_atom, _validate_type


def _get_pos_neg_examples(s: str) -> tuple[str, str] | tuple[str, str, str]:
    name = "#pos" if s.startswith("#pos") else "#neg"
    parts = split_top_level_args(_directive_args(s, name))
    if len(parts) not in (2, 3):
        raise ValueError(f"invalid example declaration: {s}")
    values = tuple(_strip_outer_braces(part.strip()) for part in parts)
    if len(values) == 2:
        return values[0], values[1]
    return values[0], values[1], values[2]


def _get_invented_declaration(s: str) -> tuple[int, AtomTemplate]:
    parts = split_top_level_args(_directive_args(s, "#invent"))
    if len(parts) != 2:
        raise ValueError(f"invalid #invent declaration: {s}")
    recall = _parse_recall(parts[0])
    atom = _get_mode_atom(parts[1], s)
    if recall < 1:
        raise ValueError(f"invalid #invent declaration: {s}")
    return recall, atom


def _get_constant_declaration(s: str) -> tuple[str, str]:
    parts = split_top_level_args(_directive_args(s, "#constant"))
    if len(parts) != 2:
        raise ValueError(f"invalid #constant declaration: {s}")
    type_name = parts[0].strip()
    _validate_type(type_name, s)
    try:
        value = str(clingo.parse_term(parts[1].strip()))
    except RuntimeError as exc:
        raise ValueError(f"#constant value must be a ground term: {s}") from exc
    return type_name, value
