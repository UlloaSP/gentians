import re
from collections.abc import Iterable
from pathlib import Path

import clingo
from clingo import ast

from .aggregate_declaration import AggregateDeclaration
from .example import Example
from .atom_literal import AtomLiteral
from .atom_template import AtomTemplate
from .comparison_literal import ComparisonLiteral
from .conditional_literal import ConditionalLiteral
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
_METARULE_DIRECTIVE = re.compile(
    r'^\s*#metarule\s*\(\s*([a-z][A-Za-z0-9_]*)\s*,\s*"((?:\\.|[^"\\])*)"\s*\)\s*\.',
    re.DOTALL | re.MULTILINE,
)


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
            predicate for predicate in defined if not predicate[0].startswith("bias_")
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


def _extract_metarules(source: str) -> tuple[str, dict[str, str]]:
    definitions: dict[str, str] = {}

    def remove(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in definitions:
            raise ValueError(f"duplicate #metarule declaration: {name}")
        payload = re.sub(
            r'\\([nrt"\\])',
            lambda escaped: _BIAS_ESCAPES[escaped.group(1)],
            match.group(2),
        ).strip()
        if not payload:
            raise ValueError(f"empty #metarule declaration: {name}")
        definitions[name] = payload
        return "\n" * match.group(0).count("\n")

    remaining = _METARULE_DIRECTIVE.sub(remove, source)
    if re.search(r"(?m)^\s*#metarule\b", remaining):
        raise ValueError("invalid #metarule declaration")
    return remaining, definitions


def _get_atom_mode_declaration(s: str, name: str) -> ModeDeclaration:
    parts = split_top_level_args(_directive_args(s, name))
    if len(parts) < 2:
        raise ValueError(f"invalid {name} declaration: {s}")
    recall = _parse_recall(parts[0])
    literal = _get_mode_literal(",".join(parts[1:]), s, conditional=True)
    return ModeDeclaration(recall, literal)


def _get_body_mode_declaration(s: str) -> ModeDeclaration:
    declaration = _get_atom_mode_declaration(s, "#modeb")
    if isinstance(declaration.literal, ComparisonLiteral):
        raise ValueError(f"#modeb comparisons belong in #modearith: {s}")
    return declaration


def _get_condition_mode_declaration(s: str) -> ModeDeclaration:
    declaration = _get_atom_mode_declaration(s, "#modec")
    if isinstance(declaration.literal, ConditionalLiteral):
        raise ValueError(f"#modec cannot contain a nested conditional literal: {s}")
    return declaration


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
    return ModeDeclaration(recall, AtomLiteral(template))


def _get_disjunctive_head_declaration(s: str) -> ModeDeclaration:
    declaration = _get_atom_mode_declaration(
        s.replace("#modehd", "#modeb", 1), "#modeb"
    )
    if (
        not isinstance(declaration.literal, AtomLiteral)
        or declaration.literal.default_negated
    ):
        raise ValueError(f"#modehd requires a positive atom: {s}")
    return declaration


def _get_head_declaration(s: str) -> HeadDeclaration:
    parts = split_top_level_args(_directive_args(s, "#modeh"))
    if len(parts) < 2:
        raise ValueError(f"invalid #modeh declaration: {s}")
    recall = _parse_recall(parts[0])
    syntax = ",".join(parts[1:]).strip()
    rules: list[ast.AST] = []
    try:
        ast.parse_string(
            f"{syntax} :- __modeh_body.",
            lambda node: (
                rules.append(node) if node.ast_type == ast.ASTType.Rule else None
            ),
        )
    except RuntimeError as exc:
        raise ValueError(f"invalid #modeh declaration: {s}") from exc
    if len(rules) != 1:
        raise ValueError(f"invalid #modeh declaration: {s}")
    head = rules[0].head
    if head.ast_type in {ast.ASTType.Literal, ast.ASTType.ConditionalLiteral}:
        literal = _literal_from_ast(head, s)
        if not isinstance(literal, AtomLiteral | ConditionalLiteral):
            raise ValueError(f"#modeh requires atom heads: {s}")
        conclusion = (
            literal.conclusion if isinstance(literal, ConditionalLiteral) else literal
        )
        if not isinstance(conclusion, AtomLiteral) or conclusion.default_negated:
            raise ValueError(f"#modeh requires positive atom heads: {s}")
        conditions = (
            literal.conditions if isinstance(literal, ConditionalLiteral) else ()
        )
        return HeadDeclaration(
            recall,
            HeadTemplate("normal", (conclusion.atom,), conditions=(conditions,)),
        )
    if head.ast_type == ast.ASTType.Disjunction:
        atoms = tuple(_head_atom(str(element.literal), s) for element in head.elements)
        conditions = tuple(
            _head_conditions(element.condition, s) for element in head.elements
        )
        return HeadDeclaration(
            recall, HeadTemplate("disjunction", atoms, conditions=conditions)
        )
    if head.ast_type == ast.ASTType.Aggregate:
        atoms = tuple(_head_atom(str(element.literal), s) for element in head.elements)
        conditions = tuple(
            _head_conditions(element.condition, s) for element in head.elements
        )
        return HeadDeclaration(
            recall,
            HeadTemplate(
                "choice",
                atoms,
                _head_bound(head.left_guard, s),
                _head_bound(head.right_guard, s),
                conditions,
            ),
        )
    raise ValueError(f"unsupported #modeh head form: {s}")


def _head_atom(raw: str, declaration: str) -> AtomTemplate:
    return _get_mode_atom(raw, declaration)


def _head_conditions(
    nodes: Iterable[ast.AST], declaration: str
) -> tuple[AtomLiteral | ComparisonLiteral, ...]:
    conditions = tuple(_literal_from_ast(item, declaration) for item in nodes)
    if any(isinstance(condition, ConditionalLiteral) for condition in conditions):
        raise ValueError(f"nested conditional literal is invalid: {declaration}")
    return tuple(
        condition
        for condition in conditions
        if isinstance(condition, AtomLiteral | ComparisonLiteral)
    )


def _head_bound(guard: ast.AST | None, declaration: str) -> int | None:
    if guard is None:
        return None
    if guard.comparison != ast.ComparisonOperator.LessEqual:
        raise ValueError(f"#modeh cardinality bounds must use <=: {declaration}")
    try:
        return int(str(guard.term))
    except ValueError as exc:
        raise ValueError(
            f"#modeh cardinality bounds must be integers: {declaration}"
        ) from exc


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


def _get_predicate_declaration(s: str) -> tuple[str, tuple[str, int]]:
    parts = split_top_level_args(_directive_args(s, "#predicate"))
    if len(parts) != 2 or not re.fullmatch(r"[a-z][A-Za-z0-9_]*", parts[0].strip()):
        raise ValueError(f"invalid #predicate declaration: {s}")
    try:
        name, arity = parts[1].strip().split("/", 1)
        signature = name, int(arity)
    except ValueError as exc:
        raise ValueError(f"invalid #predicate declaration: {s}") from exc
    if not re.fullmatch(r"[a-z][A-Za-z0-9_]*", signature[0]) or signature[1] < 0:
        raise ValueError(f"invalid #predicate declaration: {s}")
    return parts[0].strip(), signature


def _get_modem_declaration(s: str) -> tuple[str, tuple[tuple[str, int], ...]]:
    raw = _directive_args(s, "#modem").strip()
    parsed = parse_atom(raw)
    if parsed is None:
        raise ValueError(f"invalid #modem declaration: {s}")
    name, specs = parsed
    result: list[tuple[str, int]] = []
    for spec in specs:
        try:
            type_name, arity = spec.rsplit("/", 1)
            result.append((type_name.strip(), int(arity)))
        except ValueError as exc:
            raise ValueError(f"invalid #modem declaration: {s}") from exc
    return name, tuple(result)


def _instantiate_metarules(
    definitions: dict[str, str],
    predicates: dict[str, list[tuple[str, int]]],
    declarations: list[tuple[str, tuple[tuple[str, int], ...]]],
) -> tuple[tuple[str, ...], ...]:
    from itertools import product

    unused = definitions.keys() - {name for name, _specs in declarations}
    if unused:
        raise ValueError(f"unused metarule declaration: {min(unused)}")
    programs: list[tuple[str, ...]] = []
    for name, specs in declarations:
        template = definitions.get(name)
        if template is None:
            raise ValueError(f"undefined metarule: {name}")
        variables, arities = _metarule_predicates(template)
        if len(variables) != len(specs):
            raise ValueError(
                f"metarule {name} expects {len(variables)} predicate arguments, got {len(specs)}"
            )
        pools: list[tuple[tuple[str, int], ...]] = []
        for variable, (type_name, arity) in zip(variables, specs, strict=True):
            if arity != arities[variable]:
                raise ValueError(
                    f"metarule {name} predicate {variable} has arity "
                    f"{arities[variable]}, not {arity}"
                )
            candidates = tuple(
                signature
                for pool, signatures in predicates.items()
                if type_name == "any" or pool == type_name
                for signature in signatures
                if signature[1] == arity
            )
            if not candidates:
                raise ValueError(f"#modem {name} has empty pool {type_name}/{arity}")
            pools.append(candidates)
        for selected in product(*pools):
            rendered = template
            for variable, (predicate, _arity) in zip(variables, selected, strict=True):
                rendered = re.sub(
                    rf"\b{re.escape(variable)}(?=\s*\()", predicate, rendered
                )
            nodes: list[ast.AST] = []
            try:
                ast.parse_string(rendered, nodes.append)
            except RuntimeError as exc:
                raise ValueError(f"invalid instantiated metarule {name}") from exc
            if any(
                node.ast_type not in {ast.ASTType.Program, ast.ASTType.Rule}
                for node in nodes
            ):
                raise ValueError(f"metarule {name} may contain only rules")
            rules = tuple(
                str(node) for node in nodes if node.ast_type == ast.ASTType.Rule
            )
            if not rules:
                raise ValueError(f"metarule {name} contains no rules")
            try:
                control = clingo.Control(["--warn=none"])
                control.add("base", [], rendered)
                control.ground([("base", [])])
            except RuntimeError as exc:
                raise ValueError(f"unsafe instantiated metarule {name}") from exc
            programs.append(rules)
    return tuple(dict.fromkeys(programs))


def _metarule_predicates(template: str) -> tuple[tuple[str, ...], dict[str, int]]:
    variables: list[str] = []
    arities: dict[str, int] = {}
    for match in re.finditer(r"\b([A-Z][A-Za-z0-9_]*)\s*\(", template):
        variable = match.group(1)
        start = match.end()
        depth = 1
        index = start
        while index < len(template) and depth:
            depth += (template[index] == "(") - (template[index] == ")")
            index += 1
        if depth:
            raise ValueError("unclosed predicate application in metarule")
        arguments = template[start : index - 1].strip()
        arity = 0 if not arguments else len(split_top_level_args(arguments))
        previous = arities.setdefault(variable, arity)
        if previous != arity:
            raise ValueError(f"metarule predicate {variable} has inconsistent arities")
        if variable not in variables:
            variables.append(variable)
    return tuple(variables), arities


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
    lbhd: list[ModeDeclaration] = []
    lbb: list[ModeDeclaration] = []
    lbc: list[ModeDeclaration] = []
    aggregates: list[AggregateDeclaration] = []
    arithmetic: list[OperatorDeclaration | ModeDeclaration] = []
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
    source, metarule_definitions = _extract_metarules(source)
    predicate_pools: dict[str, list[tuple[str, int]]] = {}
    modem_declarations: list[tuple[str, tuple[tuple[str, int], ...]]] = []
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
            value = _get_limit(lc, limit, limit in {"#maxv", "#maxbl", "#maxhl"})
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
        elif lc.startswith("#modehd"):
            md = _get_disjunctive_head_declaration(lc)
            if md not in lbhd:
                lbhd.append(md)
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
            raise ValueError("#modecmp was removed; use #modearith")
        elif lc.startswith("#modec"):
            md = _get_condition_mode_declaration(lc)
            if md not in lbc:
                lbc.append(md)
        elif lc.startswith("#modearith"):
            operator = _get_arithmetic_declaration(lc)
            if operator not in arithmetic:
                arithmetic.append(operator)
        elif lc.startswith("#predicate"):
            pool, signature = _get_predicate_declaration(lc)
            values = predicate_pools.setdefault(pool, [])
            if signature not in values:
                values.append(signature)
        elif lc.startswith("#modem"):
            modem = _get_modem_declaration(lc)
            if modem not in modem_declarations:
                modem_declarations.append(modem)
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
        | {
            mode.literal.atom.signature
            for mode in (*lbha, *lbhd)
            if isinstance(mode.literal, AtomLiteral)
        }
        | {
            literal.atom.signature
            for mode in lbb
            for literal in (
                (mode.literal.conclusion,)
                if isinstance(mode.literal, ConditionalLiteral)
                else (mode.literal,)
            )
            if isinstance(literal, AtomLiteral)
        }
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
        for terms in [
            *(atom.terms for head in lbh for atom in head.template.elements),
            *(
                condition.arguments
                for head in lbh
                for conditions in head.template.conditions
                for condition in conditions
            ),
            *(mode.literal.arguments for mode in (*lbha, *lbhd, *lbc)),
            *(mode.literal.arguments for mode in lbb),
            *(
                mode.literal.arguments
                for mode in arithmetic
                if isinstance(mode, ModeDeclaration)
            ),
        ]
        for argument in terms
        for type_name in argument.constant_types()
    }
    missing_constants = constant_types - constants.keys()
    if missing_constants:
        raise ValueError(
            f"constant mode types require #constant declarations: {sorted(missing_constants)}"
        )
    max_head_literals = limits["#maxhl"]
    if (
        (lbha or lbhd)
        and max_head_literals is not None
        and min_head_literals > max_head_literals
    ):
        raise ValueError("#minhl cannot exceed #maxhl")
    return Program(
        background=bg,
        positive_examples=pe,
        negative_examples=ne,
        language_bias_head=lbh,
        language_bias_body=lbb,
        aggregate_modes=aggregates,
        arithmetic_modes=arithmetic,
        language_bias_condition=lbc,
        invented_predicates=invented_predicates,
        constants={name: tuple(values) for name, values in constants.items()},
        max_variables=limits["#maxv"],
        max_body_literals=limits["#maxbl"],
        max_head_literals=max_head_literals,
        max_program_clauses=limits["#maxpl"],
        language_bias_aggregate_head=lbha,
        language_bias_disjunctive_head=lbhd,
        min_aggregate_head_literals=min_head_literals,
        bias=bias,
        metarule_programs=_instantiate_metarules(
            metarule_definitions, predicate_pools, modem_declarations
        ),
    )


def _get_mode_literal(
    raw: str, declaration: str, *, conditional: bool = False
) -> AtomLiteral | ComparisonLiteral | ConditionalLiteral:
    nodes: list[ast.AST] = []
    try:
        ast.parse_string(f":- {raw.strip()}.", nodes.append)
    except RuntimeError as exc:
        raise ValueError(f"invalid mode literal: {declaration}") from exc
    rules = [node for node in nodes if node.ast_type == ast.ASTType.Rule]
    if len(rules) != 1 or len(rules[0].body) != 1:
        raise ValueError(f"mode declaration requires one literal: {declaration}")
    literal = _literal_from_ast(rules[0].body[0], declaration)
    if isinstance(literal, ConditionalLiteral) and not conditional:
        raise ValueError(f"conditional literal is not allowed here: {declaration}")
    return literal


def _literal_from_ast(
    node: ast.AST, declaration: str
) -> AtomLiteral | ComparisonLiteral | ConditionalLiteral:
    if node.ast_type == ast.ASTType.ConditionalLiteral:
        conclusion = _literal_from_ast(node.literal, declaration)
        conditions = tuple(
            _literal_from_ast(condition, declaration) for condition in node.condition
        )
        if isinstance(conclusion, ConditionalLiteral) or any(
            isinstance(condition, ConditionalLiteral) for condition in conditions
        ):
            raise ValueError(f"nested conditional literal is invalid: {declaration}")
        if not isinstance(conclusion, AtomLiteral):
            raise ValueError(f"conditional conclusions must be atoms: {declaration}")
        flat_conditions = tuple(
            condition
            for condition in conditions
            if isinstance(condition, AtomLiteral | ComparisonLiteral)
        )
        return ConditionalLiteral(
            conclusion, flat_conditions, (-1,) * len(flat_conditions)
        )
    if node.ast_type != ast.ASTType.Literal:
        raise ValueError(f"unsupported mode literal: {declaration}")
    if node.atom.ast_type == ast.ASTType.Comparison:
        if node.sign != ast.Sign.NoSign or len(node.atom.guards) != 1:
            raise ValueError(f"invalid arithmetic relation: {declaration}")
        guard = node.atom.guards[0]
        operators = {
            ast.ComparisonOperator.Equal: "=",
            ast.ComparisonOperator.NotEqual: "!=",
            ast.ComparisonOperator.LessThan: "<",
            ast.ComparisonOperator.LessEqual: "<=",
            ast.ComparisonOperator.GreaterThan: ">",
            ast.ComparisonOperator.GreaterEqual: ">=",
        }
        return ComparisonLiteral(
            operators[guard.comparison],
            (
                _term_from_ast(node.atom.term, declaration),
                _term_from_ast(guard.term, declaration),
            ),
            False,
        )
    raw = str(node)
    negative = node.sign == ast.Sign.Negation
    if node.sign == ast.Sign.DoubleNegation:
        raise ValueError(f"double default negation is unsupported: {declaration}")
    if negative:
        raw = re.sub(r"^not\s+", "", raw, count=1)
    return AtomLiteral(_get_mode_atom(raw, declaration), negative)


def _term_from_ast(node: ast.AST, declaration: str) -> TermTemplate:
    if node.ast_type == ast.ASTType.Function:
        raw_arguments = tuple(
            _term_from_ast(item, declaration) for item in node.arguments
        )
        if node.name == "var" and len(node.arguments) in {2, 3}:
            values = tuple(str(item) for item in node.arguments)
            _validate_type(values[0], declaration)
            return TermTemplate.variable(
                values[0], values[1], values[2] if len(values) == 3 else ""
            )
        if node.name == "const" and len(node.arguments) == 1:
            type_name = str(node.arguments[0])
            _validate_type(type_name, declaration)
            return TermTemplate.constant(type_name)
        if node.name in {"var", "const", "not"}:
            raise ValueError(f"invalid arithmetic placeholder: {declaration}")
        return TermTemplate("function", node.name, raw_arguments)
    if node.ast_type == ast.ASTType.BinaryOperation:
        operators = {
            ast.BinaryOperator.XOr: "^",
            ast.BinaryOperator.Or: "?",
            ast.BinaryOperator.And: "&",
            ast.BinaryOperator.Plus: "+",
            ast.BinaryOperator.Minus: "-",
            ast.BinaryOperator.Multiplication: "*",
            ast.BinaryOperator.Division: "/",
            ast.BinaryOperator.Modulo: "\\",
            ast.BinaryOperator.Power: "**",
        }
        operator = operators.get(node.operator_type)
        if operator is None:
            raise ValueError(f"unsupported arithmetic operator: {declaration}")
        return TermTemplate(
            "arithmetic",
            operator,
            (
                _term_from_ast(node.left, declaration),
                _term_from_ast(node.right, declaration),
            ),
        )
    if node.ast_type == ast.ASTType.SymbolicTerm:
        return TermTemplate.fixed(str(node.symbol))
    if node.ast_type == ast.ASTType.UnaryOperation:
        operator = {
            ast.UnaryOperator.Minus: "neg",
            ast.UnaryOperator.Negation: "bitnot",
            ast.UnaryOperator.Absolute: "absolute",
        }.get(node.operator_type)
        if operator is None:
            raise ValueError(f"unsupported unary arithmetic operator: {declaration}")
        return TermTemplate(
            "arithmetic", operator, (_term_from_ast(node.argument, declaration),)
        )
    raise ValueError(f"unsupported arithmetic term: {declaration}")
