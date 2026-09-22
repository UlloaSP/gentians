from collections.abc import Iterable, Iterator

import clingo
from clingo import ast

from ...language.asp import Predicate, clause_predicates, symbolic_function

Atom = tuple[str, tuple[ast.AST, ...], ast.Sign]


def _numeric_constants(nodes: Iterable[ast.AST]) -> dict[str, int]:
    constants: dict[str, int] = {}
    for node in nodes:
        if node.ast_type != ast.ASTType.Definition:
            continue
        value = _integer_value(node.value, constants)
        if value is not None:
            constants[str(node.name)] = value
    return constants


def _defined_predicates(nodes: tuple[ast.AST, ...]) -> set[Predicate]:
    defined: set[Predicate] = set()
    for node in nodes:
        heads, _deps, _body_literals = clause_predicates(node)
        defined.update(heads)
    return defined


def _iter_atoms(nodes: Iterable[ast.AST]) -> Iterator[Atom]:
    for node in nodes:
        yield from _node_atoms(node)


def _node_atoms(
    node: ast.AST, sign: ast.Sign = ast.Sign.NoSign
) -> tuple[Atom, ...]:
    if node.ast_type == ast.ASTType.Literal:
        return _node_atoms(
            node.atom, node.sign if node.sign != ast.Sign.NoSign else sign
        )
    if node.ast_type == ast.ASTType.SymbolicAtom:
        parsed = symbolic_function(node.symbol)
        if parsed is not None:
            name, arguments = parsed
            return ((name, tuple(arguments), sign),)
        return ()
    return tuple(
        atom
        for child in _children(node)
        for atom in _node_atoms(child, sign)
    )


def _numeric_values(node: ast.AST, constants: dict[str, int]) -> Iterator[int]:
    value = _integer_value(node, constants)
    if value is not None:
        yield value
        return
    if node.ast_type == ast.ASTType.Interval:
        start = _integer_value(node.left, constants)
        end = _integer_value(node.right, constants)
        if start is not None and end is not None and 0 <= end - start <= 10000:
            yield from range(start, end + 1)
        return
    for child in _children(node):
        yield from _numeric_values(child, constants)


def _integer_value(term: ast.AST, constants: dict[str, int]) -> int | None:
    if term.ast_type == ast.ASTType.SymbolicTerm:
        symbol = term.symbol
        if symbol.type == clingo.SymbolType.Number:
            return int(symbol.number)
        if symbol.type == clingo.SymbolType.Function and not symbol.arguments:
            return constants.get(symbol.name)
    if (
        term.ast_type == ast.ASTType.UnaryOperation
        and term.operator_type == ast.UnaryOperator.Minus
    ):
        value = _integer_value(term.argument, constants)
        return -value if value is not None else None
    return None


def _has_variable(node: ast.AST) -> bool:
    return _contains(node, ast.ASTType.Variable)


def _contains(node: ast.AST, ast_type: ast.ASTType) -> bool:
    return node.ast_type == ast_type or any(
        _contains(child, ast_type) for child in _children(node)
    )


def _children(node: ast.AST) -> Iterator[ast.AST]:
    for key in node.child_keys:
        child = getattr(node, key)
        if isinstance(child, ast.AST):
            yield child
        elif isinstance(child, ast.ASTSequence):
            yield from (item for item in child if isinstance(item, ast.AST))
