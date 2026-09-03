import re
from itertools import product

import clingo
from clingo import ast

from .asp import clause_predicates, split_top_level_args

_BIAS_DIRECTIVE = re.compile(
    r'^\s*#bias\s*\(\s*"((?:\\.|[^"\\])*)"\s*\)\s*\.\s*$',
    re.DOTALL,
)
_BIAS_ESCAPES = {"n": "\n", "r": "\r", "t": "\t", '"': '"', "\\": "\\"}
_METARULE_DIRECTIVE = re.compile(
    r'^\s*#metarule\s*\(\s*([a-z][A-Za-z0-9_]*)\s*,\s*"((?:\\.|[^"\\])*)"\s*\)\s*\.\s*$',
    re.DOTALL,
)


def _get_bias(declaration: str) -> str:
    match = _BIAS_DIRECTIVE.fullmatch(declaration)
    if match is None:
        raise ValueError("invalid #bias declaration")
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
    if len(program_directives) != 1 or str(program_directives[0]) != "#program base.":
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
    return payload


def _get_metarule(declaration: str) -> tuple[str, str]:
    match = _METARULE_DIRECTIVE.fullmatch(declaration)
    if match is None:
        raise ValueError("invalid #metarule declaration")
    name = match.group(1)
    payload = re.sub(
        r'\\([nrt"\\])',
        lambda escaped: _BIAS_ESCAPES[escaped.group(1)],
        match.group(2),
    ).strip()
    if not payload:
        raise ValueError(f"empty #metarule declaration: {name}")
    return name, payload


def _instantiate_metarules(
    definitions: dict[str, str],
    predicates: dict[str, list[tuple[str, int]]],
    declarations: list[tuple[str, tuple[tuple[str, int], ...]]],
) -> tuple[tuple[str, ...], ...]:
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
