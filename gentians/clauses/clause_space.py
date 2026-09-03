from collections.abc import Iterable

from ..language.asp import clause_predicates, parse_rule
from .clause import Clause


class ClauseSpace:
    def __init__(self, entries: list[Clause]) -> None:
        self.entries = tuple(entries)
        self.clauses = tuple(entry.text for entry in entries)
        self.statements = tuple(entry.statement for entry in entries)

    @classmethod
    def from_clauses(cls, clauses: list[str]) -> ClauseSpace:
        return cls.from_entries(_entry_from_clause(clause) for clause in clauses)

    @classmethod
    def from_entries(cls, entries: Iterable[Clause]) -> ClauseSpace:
        unique: dict[str, Clause] = {}
        for entry in entries:
            unique.setdefault(entry.text, entry)
        return cls([unique[text] for text in sorted(unique)])

    def __len__(self) -> int:
        return len(self.entries)

    def __bool__(self) -> bool:
        return bool(self.entries)


def _entry_from_clause(source: str) -> Clause:
    statement = parse_rule(source)
    heads, deps, body_literals = clause_predicates(statement)
    return Clause(source, statement, heads, deps, body_literals)
