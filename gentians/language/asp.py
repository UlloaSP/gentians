import re
from collections.abc import Iterable

import clingo
from clingo import ast
from clingo.ast import ProgramBuilder

Predicate = tuple[str, int]
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


def without_show(program: AspProgram) -> AspProgram:
    """Drop ``#show`` directives, which never change the stable models.

    Gentians reads its own shown atoms and brave/cautious consequences, and
    Clingo computes both over shown atoms only.
    """
    return tuple(
        statement
        for statement in program
        if statement.ast_type not in {ast.ASTType.ShowSignature, ast.ASTType.ShowTerm}
    )


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
    return node.ast_type == ast_type or any(
        _contains(child, ast_type) for child in _ast_children(node)
    )


def signed_predicate(name: str, arity: int, strong: bool = False) -> Predicate:
    return (f"-{name}" if strong else name), arity


def split_top_level_args(args: str) -> list[str]:
    parts: list[str] = []
    start = 0
    pairs = {"(": ")", "[": "]", "{": "}"}
    closing = set(pairs.values())
    stack: list[str] = []
    quoted = False
    escaped = False
    for index, char in enumerate(args):
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in pairs:
            stack.append(pairs[char])
        elif char in closing and stack and char == stack[-1]:
            stack.pop()
        elif char == "," and not stack:
            parts.append(args[start:index].strip())
            start = index + 1
    tail = args[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def symbolic_literal_predicate(literal: ast.AST) -> Predicate:
    """Return the signed predicate of a validated symbolic literal."""
    if (
        literal.ast_type != ast.ASTType.Literal
        or literal.atom.ast_type != ast.ASTType.SymbolicAtom
    ):
        raise ValueError(f"expected symbolic literal: {literal}")
    parsed = symbolic_function(literal.atom.symbol)
    if parsed is None:
        raise ValueError(f"expected symbolic literal: {literal}")
    name, arguments = parsed
    return name, len(arguments)


def clause_predicates(
    statement: ast.AST,
) -> tuple[frozenset[Predicate], frozenset[Predicate], int]:
    if statement.ast_type != ast.ASTType.Rule:
        return frozenset(), frozenset(), 0
    heads: set[Predicate] = set()
    deps: set[Predicate] = set()
    _collect_head_predicates(statement.head, heads, deps)
    for literal in statement.body:
        _collect_predicates(literal, deps)
    return frozenset(heads), frozenset(deps), len(statement.body)


def _collect_head_predicates(
    node: ast.AST, heads: set[Predicate], deps: set[Predicate]
) -> None:
    """Only positive head literals define; negated heads and conditions depend."""
    if node.ast_type == ast.ASTType.Literal:
        _collect_predicates(node, heads if node.sign == ast.Sign.NoSign else deps)
        return
    if node.ast_type == ast.ASTType.ConditionalLiteral:
        _collect_head_predicates(node.literal, heads, deps)
        for condition in node.condition:
            _collect_predicates(condition, deps)
        return
    if node.ast_type == ast.ASTType.TheoryAtom:
        _collect_predicates(node, heads)
        return
    for child in _ast_children(node):
        _collect_head_predicates(child, heads, deps)


def _ast_children(node: ast.AST) -> Iterable[ast.AST]:
    for key in node.child_keys:
        child = getattr(node, key)
        if isinstance(child, ast.AST):
            yield child
        elif isinstance(child, (list, ast.ASTSequence)):
            yield from (item for item in child if isinstance(item, ast.AST))


def _collect_predicates(node: ast.AST, result: set[Predicate]) -> None:
    if node.ast_type == ast.ASTType.SymbolicAtom:
        for name, arguments in symbolic_functions(node.symbol):
            result.add((name, len(arguments)))
        return
    for child in _ast_children(node):
        _collect_predicates(child, result)


def symbolic_function(symbol: ast.AST) -> tuple[str, ast.ASTSequence] | None:
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


def symbolic_functions(
    symbol: ast.AST, strong: bool = False
) -> tuple[tuple[str, ast.ASTSequence], ...]:
    """Every signed atom of a symbol, one per alternative of a top-level pool.

    Clingo represents ``p(a;b,c)`` as a pool of complete atoms, so the
    alternatives may differ in arity; ``-p(a;b)`` negates each alternative.
    """
    if symbol.ast_type == ast.ASTType.Pool:
        return tuple(
            function
            for alternative in symbol.arguments
            for function in symbolic_functions(alternative, strong)
        )
    if (
        not strong
        and symbol.ast_type == ast.ASTType.UnaryOperation
        and symbol.operator_type == ast.UnaryOperator.Minus
        and symbol.argument.ast_type == ast.ASTType.Pool
    ):
        return symbolic_functions(symbol.argument, True)
    parsed = symbolic_function(symbol)
    if parsed is None:
        return ()
    name, arguments = parsed
    return ((f"-{name}" if strong else name, arguments),)
