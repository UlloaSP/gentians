
import clingo


from .asp import parse_aggregate_spec, split_top_level_args
from .directives import _directive_args, _parse_recall, _strip_outer_braces
from .ir.aggregate_declaration import AggregateDeclaration
from .ir.comparison_literal import ComparisonLiteral
from .ir.mode_declaration import ModeDeclaration
from .ir.operator_declaration import OperatorDeclaration
from .ir.term_template import TermTemplate
from .modes import _get_mode_atom, _get_mode_literal, _validate_type


def _get_pos_neg_examples(s: str) -> tuple[str, str] | tuple[str, str, str]:
    name = "#pos" if s.startswith("#pos") else "#neg"
    parts = split_top_level_args(_directive_args(s, name))
    if len(parts) not in (2, 3):
        raise ValueError(f"invalid example declaration: {s}")
    values = tuple(_strip_outer_braces(part.strip()) for part in parts)
    if len(values) == 2:
        return values[0], values[1]
    return values[0], values[1], values[2]


def _get_aggregate_declaration(s: str) -> AggregateDeclaration:
    parts = split_top_level_args(_directive_args(s, "#modeagg"))
    if len(parts) != 3:
        raise ValueError(f"invalid #modeagg declaration: {s}")
    function, atoms = parse_aggregate_spec(parts[1])
    balance = parts[2].strip()
    if balance not in {"balanced", "unbalanced"}:
        raise ValueError(f"invalid #modeagg balance: {s}")
    return AggregateDeclaration(
        _parse_recall(parts[0]),
        function,
        atoms,
        balance == "unbalanced",
    )


def _get_operator_declaration(s: str, name: str) -> OperatorDeclaration:
    parts = split_top_level_args(_directive_args(s, name))
    if len(parts) != 2:
        raise ValueError(f"invalid {name} declaration: {s}")
    return OperatorDeclaration(_parse_recall(parts[0]), parts[1].strip())


def _get_arithmetic_declaration(s: str) -> OperatorDeclaration | ModeDeclaration:
    parts = split_top_level_args(_directive_args(s, "#modearith"))
    if len(parts) < 2:
        raise ValueError(f"invalid #modearith declaration: {s}")
    recall = _parse_recall(parts[0])
    syntax = ",".join(parts[1:]).strip()
    operators = {
        "add",
        "sub",
        "mul",
        "div",
        "mod",
        "abs",
        "eq",
        "neq",
        "lt",
        "leq",
        "gt",
        "geq",
    }
    if syntax in operators:
        return OperatorDeclaration(recall, syntax)
    literal = _get_mode_literal(syntax, s, conditional=False)
    if not isinstance(literal, ComparisonLiteral):
        raise ValueError(f"#modearith requires a relation: {s}")
    outputs = sum(
        binding.direction == "output"
        for term in literal.arguments
        for binding in term.bindings()
    )
    if outputs and (literal.operator != "=" or outputs != 1):
        raise ValueError("only arithmetic equality may declare one output")
    return ModeDeclaration(recall, literal)


def _get_invented_declaration(s: str) -> tuple[int, str, tuple[TermTemplate, ...]]:
    parts = split_top_level_args(_directive_args(s, "#invent"))
    if len(parts) != 2:
        raise ValueError(f"invalid #invent declaration: {s}")
    recall = _parse_recall(parts[0])
    atom = _get_mode_atom(parts[1], s)
    if atom.strong:
        raise ValueError(f"invented predicates cannot be strongly negated: {s}")
    if recall < 1:
        raise ValueError(f"invalid #invent declaration: {s}")
    return recall, atom.name, atom.terms


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
