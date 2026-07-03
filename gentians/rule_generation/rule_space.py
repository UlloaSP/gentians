from __future__ import annotations

from dataclasses import dataclass

from clingo import ast

Predicate = tuple[str, int]


@dataclass(frozen=True, slots=True)
class RuleEntry:
    text: str
    heads: frozenset[Predicate]
    deps: frozenset[Predicate]
    body_literals: int


class RuleSpace:
    def __init__(self, entries: list[RuleEntry]) -> None:
        self.entries = entries
        self.clauses = [entry.text for entry in entries]

    @classmethod
    def from_clauses(cls, clauses: list[str]) -> "RuleSpace":
        return cls.from_entries(_entry_from_clause(clause) for clause in clauses)

    @classmethod
    def from_entries(cls, entries) -> "RuleSpace":
        unique: dict[str, RuleEntry] = {}
        for entry in entries:
            unique.setdefault(entry.text, entry)
        return cls([unique[text] for text in sorted(unique)])

    def __len__(self) -> int:
        return len(self.entries)

    def __bool__(self) -> bool:
        return bool(self.entries)


def _entry_from_clause(rule: str) -> RuleEntry:
    heads, deps, body_literals = _rule_predicates(rule)
    return RuleEntry(rule, frozenset(heads), frozenset(deps), body_literals)


def _rule_predicates(rule: str) -> tuple[set[Predicate], set[Predicate], int]:
    rule = rule.strip()
    if not rule or rule.startswith("%"):
        return set(), set(), 0
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
        return set(), set(), 0
    return heads, deps, body_literals


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
