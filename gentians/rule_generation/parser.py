import re
from functools import lru_cache

from clingo import ast

Predicate = tuple[str, int]
ParsedAtom = tuple[str, tuple[str, ...], bool]


def split_top_level_args(args: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    pairs = {"(": ")", "[": "]", "{": "}"}
    closing = set(pairs.values())
    stack: list[str] = []
    for index, char in enumerate(args):
        if char in pairs:
            stack.append(pairs[char])
            depth += 1
        elif char in closing and stack and char == stack[-1]:
            stack.pop()
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(args[start:index].strip())
            start = index + 1
    tail = args[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def parse_predicate_specs(specs: str) -> tuple[Predicate, ...]:
    pairs: list[Predicate] = []
    for spec in split_top_level_args(specs):
        predicate, arity = spec.split("/", 1)
        pairs.append((predicate.strip(), int(arity)))
    return tuple(pairs)


def parse_aggregate_spec(spec: str) -> tuple[str, tuple[Predicate, ...]]:
    function, rest = spec.split("(", 1)
    return function.strip(), parse_predicate_specs(rest.rstrip(")"))


def extract_name_arity(atom: str) -> tuple[str, int]:
    """
    Extracts name and arity from an atom.
    """
    parsed = parse_atom(atom)
    if parsed is not None:
        function_name, arguments = parsed
        return function_name, len(arguments)
    raise ValueError(f"Error in extract_name_arity: {atom}")


def parse_atom(atom: str) -> tuple[str, list[str]] | None:
    normalized = _normal_atom_text(atom)
    if not normalized or normalized.startswith("#"):
        return None
    match = re.match(r"^([A-Za-z_]\w*)(?:\((.*)\))?$", normalized)
    if match:
        args = match.group(2)
        return match.group(1), split_top_level_args(args) if args else []
    parsed = _parse_atom_cached(normalized)
    if parsed is not None:
        name, arguments = parsed
        return name, list(arguments)
    return None


def fragment_atoms(fragment: str) -> tuple[ParsedAtom, ...]:
    return _fragment_atoms_cached(fragment.strip())


def clause_predicates(rule: str) -> tuple[frozenset[Predicate], frozenset[Predicate], int]:
    return _clause_predicates_cached(rule.strip())


def _normal_atom_text(atom: str) -> str:
    normalized = atom.strip()
    if normalized.startswith("not "):
        normalized = normalized[4:].strip()
    if normalized.startswith("{") and normalized.endswith("}"):
        normalized = normalized[1:-1].strip()
    return normalized


@lru_cache(maxsize=None)
def _fragment_atoms_cached(fragment: str) -> tuple[ParsedAtom, ...]:
    if not fragment:
        return ()
    source = fragment if fragment.endswith(".") else f":- {fragment}."
    found: list[ParsedAtom] = []
    try:
        ast.parse_string(source, lambda node: _collect_atoms(node, found))
    except RuntimeError:
        for part in split_top_level_args(fragment):
            parsed = parse_atom(part)
            if parsed is None:
                continue
            name, arguments = parsed
            found.append((name, tuple(arguments), part.strip().startswith("not ")))
    return tuple(found)


@lru_cache(maxsize=None)
def _clause_predicates_cached(
    rule: str,
) -> tuple[frozenset[Predicate], frozenset[Predicate], int]:
    if not rule or rule.startswith("%"):
        return frozenset(), frozenset(), 0
    heads: set[Predicate] = set()
    deps: set[Predicate] = set()
    body_literals = 0

    def collect(stm: ast.AST) -> None:
        nonlocal body_literals
        if "head" in stm.child_keys:
            _collect_predicates(stm.head, heads)
        if "body" in stm.child_keys:
            body_literals = len(stm.body)
            for literal in stm.body:
                _collect_predicates(literal, deps)

    try:
        ast.parse_string(rule, collect)
    except RuntimeError:
        return frozenset(), frozenset(), 0
    return frozenset(heads), frozenset(deps), body_literals


def _collect_atoms(node: ast.AST, result: list[ParsedAtom], negative: bool = False) -> None:
    if node.ast_type == ast.ASTType.Literal:
        _collect_atoms(node.atom, result, negative or node.sign != ast.Sign.NoSign)
        return
    if node.ast_type == ast.ASTType.SymbolicAtom:
        symbol = node.symbol
        if symbol.ast_type == ast.ASTType.Function and symbol.name:
            result.append(
                (
                    str(symbol.name),
                    tuple(str(argument).replace(" ", "") for argument in symbol.arguments),
                    negative,
                )
            )
        return
    for key in node.child_keys:
        child = getattr(node, key)
        if isinstance(child, ast.AST):
            _collect_atoms(child, result, negative)
        elif isinstance(child, list) or child.__class__.__name__ == "ASTSequence":
            for item in child:
                if isinstance(item, ast.AST):
                    _collect_atoms(item, result, negative)


def _collect_predicates(node: ast.AST, result: set[Predicate]) -> None:
    if node.ast_type == ast.ASTType.SymbolicAtom:
        symbol = node.symbol
        if symbol.ast_type == ast.ASTType.Function and symbol.name:
            result.add((str(symbol.name), len(symbol.arguments)))
        return
    for key in node.child_keys:
        child = getattr(node, key)
        if isinstance(child, ast.AST):
            _collect_predicates(child, result)
        elif isinstance(child, list) or child.__class__.__name__ == "ASTSequence":
            for item in child:
                if isinstance(item, ast.AST):
                    _collect_predicates(item, result)


@lru_cache(maxsize=None)
def _parse_atom_cached(atom: str) -> tuple[str, tuple[str, ...]] | None:
    found: list[tuple[str, tuple[str, ...]]] = []

    def collect(node: ast.AST) -> None:
        if node.ast_type == ast.ASTType.SymbolicAtom:
            symbol = node.symbol
            if symbol.ast_type == ast.ASTType.Function and symbol.name:
                found.append(
                    (
                        str(symbol.name),
                        tuple(
                            str(argument).replace(" ", "")
                            for argument in symbol.arguments
                        ),
                    )
                )
            return
        for key in node.child_keys:
            child = getattr(node, key)
            if isinstance(child, ast.AST):
                collect(child)
            elif isinstance(child, list) or child.__class__.__name__ == "ASTSequence":
                for item in child:
                    if isinstance(item, ast.AST):
                        collect(item)

    try:
        ast.parse_string(f":- {atom}.", collect)
    except RuntimeError:
        return None
    return found[0] if len(found) == 1 else None
