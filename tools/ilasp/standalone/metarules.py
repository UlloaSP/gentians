"""Expand a generated selector into its complete, inseparable ASP program."""

import re

from clingo import ast

from .generator import Entry, _canonical
from .task import Task, parse_asp, parse_candidate


def _unify(pattern: ast.AST, actual: ast.AST, bindings: dict[str, ast.AST]) -> bool:
    if pattern.ast_type == ast.ASTType.Variable:
        if pattern.name == "_":
            return True
        if pattern.name in bindings:
            return str(bindings[pattern.name]) == str(actual)
        bindings[pattern.name] = actual
        return True
    if pattern.ast_type == actual.ast_type == ast.ASTType.Function:
        return (pattern.name == actual.name and len(pattern.arguments) == len(actual.arguments)
                and all(_unify(p, a, bindings) for p, a in zip(pattern.arguments, actual.arguments)))
    return str(pattern) == str(actual)


class _Instantiate(ast.Transformer):
    def __init__(self, bindings: dict[str, ast.AST], names: dict[str, str]):
        self.bindings = bindings
        self.names = names

    def visit_Variable(self, node: ast.AST) -> ast.AST:
        return self.bindings.get(node.name, node)

    def visit_Function(self, node: ast.AST) -> ast.AST:
        node = node.update(**self.visit_children(node))
        if node.name in self.names:
            name = self.names[node.name]
            if name not in self.bindings:
                raise ValueError(f"unbound predicate variable in metarule: {name}")
            predicate = str(self.bindings[name])
            if not re.fullmatch(r"[a-z][A-Za-z_0-9]*", predicate):
                raise ValueError(f"metarule requires a predicate symbol: {predicate}")
            node = node.update(name=predicate)
        return node


class _NoSelectors(ast.Transformer):
    def __init__(self, signatures: set[tuple[str, int]]):
        self.signatures = signatures

    def visit_SymbolicAtom(self, node: ast.AST) -> ast.AST:
        symbol = node.symbol
        while symbol.ast_type == ast.ASTType.UnaryOperation:
            symbol = symbol.argument
        if symbol.ast_type == ast.ASTType.Function and (symbol.name, len(symbol.arguments)) in self.signatures:
            raise ValueError("residual metarule selectors require whole-hypothesis expansion")
        return node


def _positive_selector(literal: ast.AST, signatures: set[tuple[str, int]]) -> bool:
    if (literal.ast_type != ast.ASTType.Literal or literal.sign != ast.Sign.NoSign
            or literal.atom.ast_type != ast.ASTType.SymbolicAtom):
        return False
    symbol = literal.atom.symbol
    return symbol.ast_type == ast.ASTType.Function and (symbol.name, len(symbol.arguments)) in signatures


def expand_metarule(task: Task, entry: Entry) -> tuple[str, ...]:
    if not entry.meta:
        return (entry.rule,)
    selector = parse_asp(entry.rule)[0].head.atom.symbol
    signatures = set()
    for mode in task.modes:
        if mode.kind == "modem":
            symbol = parse_asp(f":- {mode.source}.")[0].body[0].atom.symbol
            signatures.add((symbol.name, len(symbol.arguments)))
    rules = []
    for source in task.background:
        nodes, names = parse_candidate(source)
        for node in nodes:
            if node.ast_type not in {ast.ASTType.Rule, ast.ASTType.Minimize}:
                continue
            # Specialisation is valid when every selector reference is an
            # independent positive body guard. Hidden/negative dependencies
            # require evaluating selectors as a whole program instead.
            _NoSelectors(signatures)(node.update(body=[b for b in node.body if not _positive_selector(b, signatures)]))
            for index, literal in enumerate(node.body):
                if (literal.ast_type != ast.ASTType.Literal or literal.sign != ast.Sign.NoSign
                        or literal.atom.ast_type != ast.ASTType.SymbolicAtom):
                    continue
                bindings: dict[str, ast.AST] = {}
                if _unify(literal.atom.symbol, selector, bindings):
                    instance = _Instantiate(bindings, names)(node)
                    body = []
                    for j, guard in enumerate(instance.body):
                        if j == index:
                            continue
                        if (guard.ast_type == ast.ASTType.Literal
                                and guard.atom.ast_type == ast.ASTType.SymbolicAtom):
                            symbol = guard.atom.symbol
                            if symbol.ast_type == ast.ASTType.Function and (symbol.name, len(symbol.arguments)) in signatures:
                                extra: dict[str, ast.AST] = {}
                                if (guard.sign == ast.Sign.NoSign and _unify(symbol, selector, extra)
                                        and not extra):
                                    continue
                                raise ValueError("coupled metarule guards require whole-hypothesis expansion")
                        body.append(guard)
                    instance = instance.update(body=body)
                    _NoSelectors(signatures)(instance)
                    rules.append(_canonical(str(instance)))
    if not rules:
        raise ValueError(f"no background template expands metarule selector: {entry.rule}")
    return tuple(sorted(set(rules)))
