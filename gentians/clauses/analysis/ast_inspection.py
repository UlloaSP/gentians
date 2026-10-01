from collections.abc import Iterable, Iterator

import clingo
from clingo import ast

from ...language.asp import Predicate, clause_predicates, symbolic_functions

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
        pending = [(node, ast.Sign.NoSign)]
        while pending:
            node, sign = pending.pop()
            if node.ast_type == ast.ASTType.Literal:
                pending.append((node.atom, node.sign if node.sign != ast.Sign.NoSign else sign))
            elif node.ast_type == ast.ASTType.SymbolicAtom:
                for name, arguments in symbolic_functions(node.symbol):
                    yield name, tuple(arguments), sign
            else:
                pending.extend((child, sign) for child in reversed(tuple(_children(node))))


def _numeric_values(node: ast.AST, constants: dict[str, int]) -> Iterator[int]:
    pending = [node]
    while pending:
        node = pending.pop()
        value = _integer_value(node, constants)
        if value is not None:
            yield value
        elif node.ast_type == ast.ASTType.Interval:
            start = _integer_value(node.left, constants)
            end = _integer_value(node.right, constants)
            if start is not None and end is not None and 0 <= end - start <= 10000:
                yield from range(start, end + 1)
        else:
            pending.extend(reversed(tuple(_children(node))))


def _integer_value(term: ast.AST, constants: dict[str, int]) -> int | None:
    sign = 1
    while (
        term.ast_type == ast.ASTType.UnaryOperation
        and term.operator_type == ast.UnaryOperator.Minus
    ):
        sign = -sign
        term = term.argument
    if term.ast_type == ast.ASTType.SymbolicTerm:
        symbol = term.symbol
        if symbol.type == clingo.SymbolType.Number:
            return sign * int(symbol.number)
        if symbol.type == clingo.SymbolType.Function and not symbol.arguments:
            value = constants.get(symbol.name)
            return sign * value if value is not None else None
    return None


def _children(node: ast.AST) -> Iterator[ast.AST]:
    for key in node.child_keys:
        child = getattr(node, key)
        if isinstance(child, ast.AST):
            yield child
        elif isinstance(child, ast.ASTSequence):
            yield from (item for item in child if isinstance(item, ast.AST))
