from collections.abc import Iterable

from .clause import Clause


class ClauseSpace:
    __slots__ = ("clauses", "entries", "statements")

    def __init__(self, entries: Iterable[Clause]) -> None:
        unique: dict[str, Clause] = {}
        for entry in entries:
            unique.setdefault(entry.text, entry)
        self.entries = tuple(unique[text] for text in sorted(unique))
        self.clauses = tuple(entry.text for entry in self.entries)
        self.statements = tuple(entry.statement for entry in self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    def __bool__(self) -> bool:
        return bool(self.entries)
