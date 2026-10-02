import re
from collections.abc import Iterable

import clingo
from clingo import ast
from clingo.ast import ProgramBuilder

from .grammar import DELIMITERS, SourceError, quoted_end
from .lexer import has_task_extensions

Predicate = tuple[str, int]
AspProgram = tuple[ast.AST, ...]


def _diagnostic_detail(message: str) -> str:
    return re.sub(r"(?m)^<string>:\d+:\d+(?:-\d+)?:[ \t]*", "", message).strip()


def parse_program(source: str, line: int = 1, column: int = 1) -> AspProgram:
    """Parse ASP with Clingo and discard its implicit ``#program base`` node."""
    statements: list[ast.AST] = []
    diagnostics: list[str] = []
    try:
        ast.parse_string(
            source,
            statements.append,
            logger=lambda _code, message: diagnostics.append(message),
        )
    except RuntimeError:
        diagnostic = "\n".join(diagnostics).strip()
        match = re.search(r"(?m)^<string>:(\d+):(\d+)", diagnostic)
        error_line = line + int(match.group(1)) - 1 if match else line
        error_column = int(match.group(2)) + (column - 1 if match.group(1) == "1" else 0) if match else column
        detail = _diagnostic_detail(diagnostic)
        raise SourceError(error_line, f"invalid ASP program: {detail or source.strip()}", column=error_column) from None
    if statements and _is_implicit_base(statements[0]):
        statements.pop(0)
    return tuple(statement for statement in statements if statement.ast_type != ast.ASTType.Comment)


def validate_task_program(source: str, program: Iterable[ast.AST], line: int = 1, column: int = 1) -> None:
    """Reject task features requiring unsupported theory or host contexts.

    The introducers only gate inspection; native nodes decide validity, so
    their occurrences inside strings and comments remain ordinary ASP data.
    """
    if not has_task_extensions(source):
        return
    pending = list(reversed(tuple(program)))
    while pending:
        node = pending.pop()
        node_type = node.ast_type
        message = None
        if node_type in {ast.ASTType.TheoryAtom, ast.ASTType.TheoryDefinition}:
            message = "theory atoms and definitions are unsupported in task files"
        elif node_type == ast.ASTType.Function and node.external:
            message = "external function terms are unsupported in task files"
        if message is not None:
            position = node.location.begin
            raise SourceError(
                line + position.line - 1, message,
                column=position.column + (column - 1 if position.line == 1 else 0),
            )
        pending.extend(reversed(tuple(_ast_children(node))))


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


def parse_rule(source: str, line: int = 1, column: int = 1) -> ast.AST:
    statements = parse_program(source, line, column)
    if len(statements) != 1 or statements[0].ast_type != ast.ASTType.Rule:
        raise ValueError(f"expected one ASP rule: {source}")
    return statements[0]


def parse_example_fields(
    included: tuple[str, int, int],
    excluded: tuple[str, int, int],
    context: tuple[str, int, int],
    cache: dict[tuple[bool, str], AspProgram],
) -> tuple[tuple[ast.AST, ...], tuple[ast.AST, ...], AspProgram]:
    """Parse each non-empty ASP-owned field of one example with Clingo."""
    result = []
    for ground, (source, line, column) in ((True, included), (True, excluded), (False, context)):
        key = ground, source
        if key not in cache:
            if ground:
                parsed = _parse_ground_atoms(source, line, column)
            else:
                parsed = parse_program(source, line, column) if source else ()
                validate_task_program(source, parsed, line, column)
                for statement in parsed:
                    if statement.ast_type != ast.ASTType.Rule:
                        raise SourceError.at_node(statement, "unsupported statement in example context: "
                                                  f"{statement.ast_type}").with_origin(line, column)
            cache[key] = parsed
        result.append(cache[key])
    return result[0], result[1], result[2]


def _parse_ground_atoms(source: str, line: int, column: int) -> tuple[ast.AST, ...]:
    if not source.strip():
        return ()
    atoms = tuple(parse_rule(f":- {source}.", line, column - 3).body)
    _validate_ground_atoms(atoms, source, line, column - 3)
    validate_task_program(source, atoms, line, column - 3)
    return atoms


def _validate_ground_atoms(atoms: tuple[ast.AST, ...], source: str, line: int, column: int) -> None:
    for literal in atoms:
        invalid = (
            literal if literal.ast_type != ast.ASTType.Literal
            or literal.sign != ast.Sign.NoSign
            or literal.atom.ast_type != ast.ASTType.SymbolicAtom
            else _invalid_ground_term(literal.atom.symbol)
        )
        if invalid is not None:
            raise SourceError.at_node(invalid, f"examples require ground symbolic atoms: {source}").with_origin(line, column)


def _invalid_ground_term(term: ast.AST) -> ast.AST | None:
    pending = [term]
    while pending:
        node = pending.pop()
        if node.ast_type in {ast.ASTType.Variable, ast.ASTType.Pool, ast.ASTType.Interval}:
            return node
        pending.extend(reversed(tuple(_ast_children(node))))
    return None


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


def has_variable(term: ast.AST) -> bool:
    """Inspect native ASP terms, including ordinary functions named var/const."""
    pending = [term]
    while pending:
        node = pending.pop()
        match node.ast_type:
            case ast.ASTType.Variable:
                return True
            case ast.ASTType.Function | ast.ASTType.Pool:
                pending.extend(node.arguments)
            case ast.ASTType.BinaryOperation | ast.ASTType.Interval:
                pending.extend((node.left, node.right))
            case ast.ASTType.UnaryOperation:
                pending.append(node.argument)
            case ast.ASTType.SymbolicTerm:
                pass
            case _:
                pending.extend(_ast_children(node))
    return False


def signed_predicate(name: str, arity: int, strong: bool = False) -> Predicate:
    return (f"-{name}" if strong else name), arity


def split_top_level_args(args: str) -> list[tuple[int, int]]:
    """Return trimmed argument spans without losing their source offsets."""
    parts: list[tuple[int, int]] = []
    start = 0
    stack: list[str] = []
    index = 0
    while index < len(args):
        char = args[index]
        if char == '"':
            index = quoted_end(args, index)
            continue
        if char in DELIMITERS:
            stack.append(DELIMITERS[char])
        elif char in ")]}":
            if not stack or stack[-1] != char:
                raise ValueError(f"unmatched {char}")
            stack.pop()
        elif char == "," and not stack:
            left, right = start, index
            while left < right and args[left].isspace():
                left += 1
            while right > left and args[right - 1].isspace():
                right -= 1
            parts.append((left, right))
            start = index + 1
        index += 1
    if stack:
        raise ValueError(f"unclosed delimiter, expected {stack[-1]}")
    end = len(args)
    while start < end and args[start].isspace():
        start += 1
    while end > start and args[end - 1].isspace():
        end -= 1
    if parts and start == end:
        raise ValueError("empty top-level argument")
    if start < end:
        parts.append((start, end))
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
    if statement.ast_type == ast.ASTType.TheoryDefinition:
        raise ValueError("theory definitions are unsupported")
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
    pending = [node]
    while pending:
        node = pending.pop()
        if node.ast_type == ast.ASTType.Literal:
            _collect_predicates(node, heads if node.sign == ast.Sign.NoSign else deps)
        elif node.ast_type == ast.ASTType.ConditionalLiteral:
            pending.append(node.literal)
            for condition in node.condition:
                _collect_predicates(condition, deps)
        elif node.ast_type == ast.ASTType.TheoryAtom:
            raise ValueError("theory atoms are unsupported")
        else:
            pending.extend(_ast_children(node))


def _ast_children(node: ast.AST) -> Iterable[ast.AST]:
    for key in node.child_keys:
        child = getattr(node, key)
        if isinstance(child, ast.AST):
            yield child
        elif isinstance(child, (list, ast.ASTSequence)):
            yield from (item for item in child if isinstance(item, ast.AST))


def _collect_predicates(node: ast.AST, result: set[Predicate]) -> None:
    pending = [node]
    while pending:
        node = pending.pop()
        if node.ast_type == ast.ASTType.TheoryAtom:
            raise ValueError("theory atoms are unsupported")
        if node.ast_type == ast.ASTType.SymbolicAtom:
            for name, arguments in symbolic_functions(node.symbol):
                result.add((name, len(arguments)))
        else:
            pending.extend(_ast_children(node))


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
    result = []
    pending = [(symbol, strong)]
    while pending:
        symbol, strong = pending.pop()
        if symbol.ast_type == ast.ASTType.Pool:
            pending.extend((item, strong) for item in reversed(symbol.arguments))
        elif (
            not strong
            and symbol.ast_type == ast.ASTType.UnaryOperation
            and symbol.operator_type == ast.UnaryOperator.Minus
            and symbol.argument.ast_type == ast.ASTType.Pool
        ):
            pending.append((symbol.argument, True))
        elif (parsed := symbolic_function(symbol)) is not None:
            name, arguments = parsed
            result.append((f"-{name}" if strong else name, arguments))
    return tuple(result)
