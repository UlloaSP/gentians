import re
from pathlib import Path

import clingo
from clingo import ast

from .aggregate_declaration import AggregateDeclaration
from .example import Example
from .atom_literal import AtomLiteral
from .atom_template import AtomTemplate
from .head_declaration import HeadDeclaration
from .head_template import HeadTemplate
from .mode_declaration import ModeDeclaration
from .operator_declaration import OperatorDeclaration
from .parser import (
    clause_predicates,
    parse_aggregate_spec,
    parse_atom,
    split_top_level_args,
)
from .program import Program
from .term_template import TermTemplate


_BIAS_DIRECTIVE = re.compile(
    r'^\s*#bias\s*\(\s*"((?:\\.|[^"\\])*)"\s*\)\s*\.',
    re.DOTALL | re.MULTILINE,
)
_BIAS_ESCAPES = {"n": "\n", "r": "\r", "t": "\t", '"': '"', "\\": "\\"}


def _extract_bias(source: str) -> tuple[str, tuple[str, ...]]:
    bias: list[str] = []

    def remove(match: re.Match[str]) -> str:
        payload = re.sub(
            r'\\([nrt"\\])',
            lambda escaped: _BIAS_ESCAPES[escaped.group(1)],
            match.group(1),
        ).strip()
        if not payload:
            raise ValueError("#bias requires a non-empty ASP program")
        nodes: list[ast.AST] = []
        try:
            ast.parse_string(payload, nodes.append)
        except RuntimeError as exc:
            raise ValueError("invalid ASP program in #bias") from exc
        unsupported = {
            node.ast_type.name
            for node in nodes
            if node.ast_type not in {ast.ASTType.Program, ast.ASTType.Rule}
        }
        if unsupported:
            raise ValueError(
                "#bias supports only ASP rules and hard constraints, not "
                f"{sorted(unsupported)}"
            )
        program_directives = [
            node for node in nodes if node.ast_type == ast.ASTType.Program
        ]
        if (
            len(program_directives) != 1
            or str(program_directives[0]) != "#program base."
        ):
            raise ValueError("#bias cannot contain #program directives")
        rules = [node for node in nodes if node.ast_type == ast.ASTType.Rule]
        if not rules:
            raise ValueError("#bias requires at least one ASP rule or hard constraint")
        defined = set().union(*(clause_predicates(str(rule))[0] for rule in rules))
        invalid = {
            predicate
            for predicate in defined
            if not predicate[0].startswith("bias_")
        }
        if invalid:
            raise ValueError(
                "predicates defined by #bias must use the bias_ namespace: "
                f"{sorted(invalid)}"
            )
        bias.append(payload)
        return "\n" * match.group(0).count("\n")

    remaining = _BIAS_DIRECTIVE.sub(remove, source)
    if re.search(r"(?m)^\s*#bias\b", remaining):
        raise ValueError("invalid #bias declaration")
    return remaining, tuple(bias)


def _get_atom_mode_declaration(s: str, name: str) -> ModeDeclaration:
    parts = split_top_level_args(_directive_args(s, name))
    if len(parts) != 2:
        raise ValueError(f"invalid {name} declaration: {s}")
    recall = _parse_recall(parts[0])
    atom = parts[1].strip()
    negative = bool(re.match(r"not\s+", atom))
    if negative:
        atom = re.sub(r"^not\s+", "", atom, count=1)
    template = _get_mode_atom(atom, s)
    if any(binding.label for binding in template.bindings()):
        raise ValueError(f"variable labels are only supported in #modeh: {s}")
    return ModeDeclaration(recall, AtomLiteral(template, negative))


def _get_body_mode_declaration(s: str) -> ModeDeclaration:
    return _get_atom_mode_declaration(s, "#modeb")


def _get_condition_mode_declaration(s: str) -> ModeDeclaration:
    return _get_atom_mode_declaration(s, "#modec")


def _get_aggregate_head_declaration(s: str) -> ModeDeclaration:
    parts = split_top_level_args(_directive_args(s, "#modeha"))
    if len(parts) == 1:
        recall = -1
        atom = parts[0]
    elif len(parts) == 2:
        recall = _parse_recall(parts[0])
        atom = parts[1]
    else:
        raise ValueError(f"invalid #modeha declaration: {s}")
    template = _get_mode_atom(atom, s)
    if any(binding.label for binding in template.bindings()):
        raise ValueError(f"variable labels are only supported in #modeh: {s}")
    return ModeDeclaration(recall, AtomLiteral(template))


def _get_head_declaration(s: str) -> HeadDeclaration:
    parts = split_top_level_args(_directive_args(s, "#modeh"))
    if len(parts) != 2:
        raise ValueError(f"invalid #modeh declaration: {s}")
    recall = _parse_recall(parts[0])
    rules: list[ast.AST] = []
    try:
        ast.parse_string(
            f"{parts[1].strip()} :- __modeh_body.",
            lambda node: rules.append(node)
            if node.ast_type == ast.ASTType.Rule
            else None,
        )
    except RuntimeError as exc:
        raise ValueError(f"invalid #modeh declaration: {s}") from exc
    if len(rules) != 1:
        raise ValueError(f"invalid #modeh declaration: {s}")
    head = rules[0].head
    if head.ast_type == ast.ASTType.Literal:
        atoms = (_head_atom(str(head), s),)
        return HeadDeclaration(recall, HeadTemplate("normal", atoms))
    if head.ast_type == ast.ASTType.Disjunction:
        if any(element.condition for element in head.elements):
            raise ValueError(f"conditional disjunction is not supported in #modeh: {s}")
        atoms = tuple(_head_atom(str(element.literal), s) for element in head.elements)
        return HeadDeclaration(recall, HeadTemplate("disjunction", atoms))
    if head.ast_type == ast.ASTType.Aggregate:
        if any(element.condition for element in head.elements):
            raise ValueError(
                f"conditional choice/cardinality is not supported in #modeh: {s}"
            )
        atoms = tuple(_head_atom(str(element.literal), s) for element in head.elements)
        return HeadDeclaration(
            recall,
            HeadTemplate(
                "choice",
                atoms,
                _head_bound(head.left_guard, s),
                _head_bound(head.right_guard, s),
            ),
        )
    raise ValueError(f"unsupported #modeh head form: {s}")


def _head_atom(raw: str, declaration: str) -> AtomTemplate:
    return _get_mode_atom(raw, declaration)


def _head_bound(guard: ast.AST | None, declaration: str) -> int | None:
    if guard is None:
        return None
    if guard.comparison != ast.ComparisonOperator.LessEqual:
        raise ValueError(f"#modeh cardinality bounds must use <=: {declaration}")
    try:
        return int(str(guard.term))
    except ValueError as exc:
        raise ValueError(f"#modeh cardinality bounds must be integers: {declaration}") from exc


def _get_mode_atom(raw: str, declaration: str) -> AtomTemplate:
    raw = raw.strip()
    if raw == "not" or re.match(r"not\s+", raw):
        raise ValueError(f"invalid mode atom: {declaration}")
    strong = raw.startswith("-")
    if strong:
        raw = raw[1:].strip()
    if raw.startswith("-"):
        raise ValueError(f"invalid mode atom: {declaration}")
    parsed = parse_atom(raw)
    if parsed is None:
        raise ValueError(f"invalid mode atom: {declaration}")
    name, raw_arguments = parsed
    if name == "not" or not re.fullmatch(r"[a-z][A-Za-z0-9_]*", name):
        raise ValueError(f"invalid mode predicate: {declaration}")
    return AtomTemplate(
        name,
        tuple(_get_mode_argument(argument, declaration) for argument in raw_arguments),
        strong,
    )


def _get_mode_argument(raw: str, declaration: str) -> TermTemplate:
    raw = raw.strip()
    if raw.startswith("(") and raw.endswith(")"):
        inner = raw[1:-1].strip()
        parts = split_top_level_args(inner)
        if len(parts) == 1 and not inner.endswith(","):
            raise ValueError(f"invalid mode tuple: {declaration}")
        return TermTemplate(
            "tuple",
            arguments=tuple(_get_mode_argument(part, declaration) for part in parts),
        )
    parsed = parse_atom(raw)
    if parsed is None:
        raise ValueError(f"invalid mode argument: {declaration}")
    kind, parts = parsed
    if kind == "var" and len(parts) in {2, 3}:
        type_name, direction = (part.strip() for part in parts[:2])
        label = parts[2].strip() if len(parts) == 3 else ""
        _validate_type(type_name, declaration)
        return TermTemplate.variable(type_name, direction, label)
    if kind == "const" and len(parts) == 1:
        type_name = parts[0].strip()
        _validate_type(type_name, declaration)
        return TermTemplate.constant(type_name)
    if kind in {"var", "const", "not"} or not parts:
        raise ValueError(f"invalid mode argument: {declaration}")
    if not re.fullmatch(r"[a-z][A-Za-z0-9_]*", kind):
        raise ValueError(f"invalid mode function: {declaration}")
    return TermTemplate(
        "function",
        kind,
        tuple(_get_mode_argument(part, declaration) for part in parts),
    )


def _validate_type(type_name: str, declaration: str) -> None:
    if type_name == "any" or not re.fullmatch(r"[a-z][A-Za-z0-9_]*", type_name):
        raise ValueError(f"invalid mode type in declaration: {declaration}")


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


def _directive_args(line: str, name: str) -> str:
    line = line.strip()
    if not line.startswith(f"{name}(") or not line.endswith(")."):
        raise ValueError(f"invalid directive: {line}")
    return line[len(name) + 1 : -2]


def _parse_recall(raw: str) -> int:
    raw = raw.strip()
    return -1 if raw == "*" else int(raw)


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


def _strip_outer_braces(value: str) -> str:
    value = value.strip()
    if not (value.startswith("{") and value.endswith("}")):
        raise ValueError(f"expected braced value: {value}")
    return value[1:-1].strip()


def read_program(filename: str) -> Program:
    """
    Read the inductive task from file.
    """
    bg: list[str] = []
    pe: list[Example] = []
    ne: list[Example] = []
    lbh: list[HeadDeclaration] = []
    lbha: list[ModeDeclaration] = []
    lbb: list[ModeDeclaration] = []
    lbc: list[ModeDeclaration] = []
    aggregates: list[AggregateDeclaration] = []
    comparisons: list[OperatorDeclaration] = []
    arithmetic: list[OperatorDeclaration] = []
    inventions: list[tuple[int, str, tuple[TermTemplate, ...]]] = []
    constants: dict[str, list[str]] = {}
    limits: dict[str, int | None] = {
        "#maxv": 3,
        "#maxbl": 3,
        "#maxhl": 1,
        "#maxpl": 6,
    }
    min_head_literals = 1
    declared_limits: set[str] = set()

    source, bias = _extract_bias(Path(filename).read_text(encoding="utf-8"))
    for line in source.splitlines():
        lc = line.rstrip().lstrip()
        if not lc or lc.startswith("%"):
            continue

        limit = next(
            (
                name
                for name in ("#maxv", "#maxbl", "#maxhl", "#maxpl", "#minhl")
                if lc.startswith(f"{name}(")
            ),
            None,
        )
        if limit is not None:
            if limit in declared_limits:
                raise ValueError(f"duplicate {limit} declaration: {lc}")
            declared_limits.add(limit)
            value = _get_limit(
                lc, limit, limit in {"#maxv", "#maxbl", "#maxhl"}
            )
            if limit == "#minhl":
                if value is None:
                    raise ValueError(f"invalid #minhl declaration: {lc}")
                min_head_literals = value
            else:
                limits[limit] = value
        elif lc.startswith("#modeha"):
            md = _get_aggregate_head_declaration(lc)
            if md not in lbha:
                lbha.append(md)
        elif lc.startswith("#modeh"):
            md = _get_head_declaration(lc)
            if md not in lbh:
                lbh.append(md)
        elif lc.startswith("#modeb"):
            md = _get_body_mode_declaration(lc)
            if md not in lbb:
                lbb.append(md)
        elif lc.startswith("#pos"):
            res = _get_pos_neg_examples(lc)
            ex = Example(res, True)
            if ex not in pe:
                pe.append(ex)
        elif lc.startswith("#neg"):
            res = _get_pos_neg_examples(lc)
            ex = Example(res, False)
            if ex not in ne:
                ne.append(ex)
        elif lc.startswith("#modeagg"):
            aggregate = _get_aggregate_declaration(lc)
            if aggregate not in aggregates:
                aggregates.append(aggregate)
        elif lc.startswith("#modecmp"):
            comparison = _get_operator_declaration(lc, "#modecmp")
            if comparison not in comparisons:
                comparisons.append(comparison)
        elif lc.startswith("#modec"):
            md = _get_condition_mode_declaration(lc)
            if md not in lbc:
                lbc.append(md)
        elif lc.startswith("#modearith"):
            operator = _get_operator_declaration(lc, "#modearith")
            if operator not in arithmetic:
                arithmetic.append(operator)
        elif lc.startswith("#invent"):
            invention = _get_invented_declaration(lc)
            if any(existing[1:] == invention[1:] for existing in inventions):
                raise ValueError(f"duplicate #invent declaration: {lc}")
            inventions.append(invention)
        elif lc.startswith("#constant"):
            type_name, value = _get_constant_declaration(lc)
            values = constants.setdefault(type_name, [])
            if value not in values:
                values.append(value)
        else:
            bg.append(lc)

    invented_predicates = tuple(
        (name, len(arguments)) for _recall, name, arguments in inventions
    )
    explicit = (
        {atom.signature for head in lbh for atom in head.template.elements}
        | {mode.literal.atom.signature for mode in lbha}
        | {mode.literal.atom.signature for mode in lbb}
    )
    overlap = explicit.intersection(invented_predicates)
    if overlap:
        raise ValueError(
            "invented predicates must not also use #modeh/#modeha/#modeb: "
            f"{sorted(overlap)}"
        )
    for recall, name, arguments in inventions:
        lbh.append(
            HeadDeclaration(1, HeadTemplate("normal", (AtomTemplate(name, arguments),)))
        )
        lbb.append(ModeDeclaration(recall, AtomLiteral(AtomTemplate(name, arguments))))
    constant_types = {
        type_name
        for atom in [
            *(atom for head in lbh for atom in head.template.elements),
            *(mode.literal.atom for mode in lbha),
            *(mode.literal.atom for mode in (*lbb, *lbc)),
        ]
        for argument in atom.terms
        for type_name in argument.constant_types()
    }
    missing_constants = constant_types - constants.keys()
    if missing_constants:
        raise ValueError(
            f"constant mode types require #constant declarations: {sorted(missing_constants)}"
        )
    max_head_literals = limits["#maxhl"]
    if (
        lbha
        and max_head_literals is not None
        and min_head_literals > max_head_literals
    ):
        raise ValueError("#minhl cannot exceed #maxhl")
    return Program(
        bg,
        pe,
        ne,
        lbh,
        lbb,
        aggregates,
        comparisons,
        arithmetic,
        language_bias_condition=lbc,
        invented_predicates=invented_predicates,
        constants={name: tuple(values) for name, values in constants.items()},
        max_variables=limits["#maxv"],
        max_body_literals=limits["#maxbl"],
        max_head_literals=max_head_literals,
        max_program_clauses=limits["#maxpl"],
        language_bias_aggregate_head=lbha,
        min_aggregate_head_literals=min_head_literals,
        bias=bias,
    )
