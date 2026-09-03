from collections.abc import Iterable
from functools import lru_cache
import re

import clingo
from clingo import ast
from clingo.ast import ProgramBuilder

Predicate = tuple[str, int]
ParsedAtom = tuple[str, tuple[str, ...], bool]
AspProgram = tuple[ast.AST, ...]


def parse_program(source: str, line: int = 1) -> AspProgram:
    """Parse ASP with Clingo and discard its implicit ``#program base`` node."""
    statements: list[ast.AST] = []
    try:
        ast.parse_string(source, statements.append)
    except RuntimeError:
        error_line = _parse_error_line(source, line)
        raise ValueError(
            f"line {error_line}: invalid ASP program: {source.strip()}"
        ) from None
    if statements and _is_implicit_base(statements[0]):
        statements.pop(0)
    return tuple(statements)


def _parse_error_line(source: str, line: int) -> int:
    diagnostics: list[str] = []
    try:
        ast.parse_string(
            source,
            lambda _statement: None,
            logger=lambda _code, message: diagnostics.append(message),
        )
    except RuntimeError:
        pass
    match = re.search(r"<string>:(\d+):", "\n".join(diagnostics))
    return line + int(match.group(1)) - 1 if match else line


def parse_rule(source: str) -> ast.AST:
    statements = parse_program(source)
    if len(statements) != 1 or statements[0].ast_type != ast.ASTType.Rule:
        raise ValueError(f"expected one ASP rule: {source}")
    return statements[0]


def parse_example_fields(
    included_source: str,
    excluded_source: str,
    context_source: str,
) -> tuple[tuple[ast.AST, ...], tuple[ast.AST, ...], AspProgram]:
    """Parse each non-empty ASP-owned field of one example with Clingo."""
    return (
        _parse_ground_atoms(included_source),
        _parse_ground_atoms(excluded_source),
        parse_program(context_source) if context_source else (),
    )


def _parse_ground_atoms(source: str) -> tuple[ast.AST, ...]:
    if not source.strip():
        return ()
    atoms = tuple(parse_rule(f":- {source}.").body)
    _validate_ground_atoms(atoms, source)
    return atoms


def _validate_ground_atoms(atoms: tuple[ast.AST, ...], source: str) -> None:
    if any(
        literal.ast_type != ast.ASTType.Literal
        or literal.sign != ast.Sign.NoSign
        or literal.atom.ast_type != ast.ASTType.SymbolicAtom
        or _contains(literal, ast.ASTType.Variable)
        for literal in atoms
    ):
        raise ValueError(f"examples require ground symbolic atoms: {source}")


def add_program(control: clingo.Control, statements: Iterable[ast.AST]) -> None:
    """Add already parsed ASP statements to a control without reparsing text."""
    with ProgramBuilder(control) as builder:
        for statement in statements:
            builder.add(statement)


def render_program(statements: Iterable[ast.AST]) -> tuple[str, ...]:
    return tuple(str(statement) for statement in statements)


def render_literals(literals: Iterable[ast.AST]) -> str:
    return ",".join(str(literal) for literal in literals)


def _is_implicit_base(statement: ast.AST) -> bool:
    return statement.ast_type == ast.ASTType.Program and str(statement) == "#program base."


def _contains(node: ast.AST, ast_type: ast.ASTType) -> bool:
    if node.ast_type == ast_type:
        return True
    for key in node.child_keys:
        child = getattr(node, key)
        if isinstance(child, ast.AST) and _contains(child, ast_type):
            return True
        if isinstance(child, list) or child.__class__.__name__ == "ASTSequence":
            if any(isinstance(item, ast.AST) and _contains(item, ast_type) for item in child):
                return True
    return False


def signed_predicate(name: str, arity: int, strong: bool = False) -> Predicate:
    return (f"-{name}" if strong else name), arity


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
    parsed = parse_function(atom)
    if parsed is not None:
        name, arguments = parsed
        return name, [str(argument).replace(" ", "") for argument in arguments]
    return None


def parse_function(atom: str) -> tuple[str, tuple[ast.AST, ...]] | None:
    """Parse one symbolic atom using Clingo's grammar."""
    return _parse_function_cached(_normal_atom_text(atom))


def fragment_atoms(fragment: str) -> tuple[ParsedAtom, ...]:
    return _fragment_atoms_cached(fragment.strip())


def clause_predicates(
    rule: str | ast.AST,
) -> tuple[frozenset[Predicate], frozenset[Predicate], int]:
    if isinstance(rule, ast.AST):
        return _clause_predicates_ast(rule)
    return _clause_predicates_cached(rule.strip())


def symbolic_literal_predicate(literal: ast.AST) -> Predicate:
    """Return the signed predicate of a validated symbolic literal."""
    if (
        literal.ast_type != ast.ASTType.Literal
        or literal.atom.ast_type != ast.ASTType.SymbolicAtom
    ):
        raise ValueError(f"expected symbolic literal: {literal}")
    parsed = _symbolic_function(literal.atom.symbol)
    if parsed is None:
        raise ValueError(f"expected symbolic literal: {literal}")
    name, arguments = parsed
    return name, len(arguments)


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
        return ()
    return tuple(found)


@lru_cache(maxsize=None)
def _clause_predicates_cached(
    rule: str,
) -> tuple[frozenset[Predicate], frozenset[Predicate], int]:
    if not rule or rule.startswith("%"):
        return frozenset(), frozenset(), 0
    statements: list[ast.AST] = []
    try:
        ast.parse_string(rule, statements.append)
    except RuntimeError:
        return frozenset(), frozenset(), 0
    parsed = next(
        (statement for statement in statements if statement.ast_type == ast.ASTType.Rule),
        None,
    )
    return (
        _clause_predicates_ast(parsed)
        if parsed is not None
        else (frozenset(), frozenset(), 0)
    )


def _clause_predicates_ast(
    statement: ast.AST,
) -> tuple[frozenset[Predicate], frozenset[Predicate], int]:
    if statement.ast_type != ast.ASTType.Rule:
        return frozenset(), frozenset(), 0
    heads: set[Predicate] = set()
    deps: set[Predicate] = set()
    _collect_predicates(statement.head, heads)
    for literal in statement.body:
        _collect_predicates(literal, deps)
    return frozenset(heads), frozenset(deps), len(statement.body)


def _collect_atoms(node: ast.AST, result: list[ParsedAtom], negative: bool = False) -> None:
    if node.ast_type == ast.ASTType.Literal:
        _collect_atoms(node.atom, result, negative or node.sign != ast.Sign.NoSign)
        return
    if node.ast_type == ast.ASTType.SymbolicAtom:
        parsed = _symbolic_function(node.symbol)
        if parsed is not None:
            name, arguments = parsed
            result.append(
                (
                    name,
                    tuple(str(argument).replace(" ", "") for argument in arguments),
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
        parsed = _symbolic_function(node.symbol)
        if parsed is not None:
            name, arguments = parsed
            result.add((name, len(arguments)))
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
def _parse_function_cached(atom: str) -> tuple[str, tuple[ast.AST, ...]] | None:
    if not atom or atom.startswith("#"):
        return None
    try:
        statements = parse_program(f":- {atom}.")
    except RuntimeError:
        return None
    except ValueError:
        return None
    rules = [node for node in statements if node.ast_type == ast.ASTType.Rule]
    if len(rules) != 1 or len(rules[0].body) != 1:
        return None
    literal = rules[0].body[0]
    if (
        literal.ast_type != ast.ASTType.Literal
        or literal.atom.ast_type != ast.ASTType.SymbolicAtom
    ):
        return None
    parsed = _symbolic_function(literal.atom.symbol)
    if parsed is None:
        return None
    name, arguments = parsed
    return name, tuple(arguments)


def _symbolic_function(symbol: ast.AST) -> tuple[str, ast.ASTSequence] | None:
    strong = False
    if symbol.ast_type == ast.ASTType.UnaryOperation:
        if symbol.operator_type != ast.UnaryOperator.Minus:
            return None
        strong = True
        symbol = symbol.argument
    if symbol.ast_type != ast.ASTType.Function or not symbol.name:
        return None
    name = f"-{symbol.name}" if strong else str(symbol.name)
    return name, symbol.arguments
