from __future__ import annotations

from dataclasses import dataclass

from .parser import clause_predicates

Predicate = tuple[str, int]


@dataclass(frozen=True, slots=True)
class RuleEntry:
    text: str
    heads: frozenset[Predicate]
    deps: frozenset[Predicate]
    body_literals: int


class RuleSpace:
    def __init__(self, entries: list[RuleEntry]) -> None:
        self.entries = tuple(entries)
        self.clauses = tuple(entry.text for entry in entries)

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
    heads, deps, body_literals = clause_predicates(rule)
    return RuleEntry(rule, heads, deps, body_literals)
