from collections.abc import Iterable
from typing import cast
from dataclasses import replace

from .clause import Clause


class ClauseSpace:
    __slots__ = ("clauses", "entries")

    def __init__(self, entries: Iterable[Clause] | dict[str, Clause], *, pack: bool = False) -> None:
        unique: dict[str, Clause]
        if isinstance(entries, dict):
            # Transfer an already deduplicated text index, then release it.
            unique = cast(dict[str, Clause], entries)
        else:
            unique = {}
            for entry in entries:
                current = unique.get(entry.text)
                # Distinct arithmetic keys can render identical native syntax.
                # Keep the cheapest legal source rather than whichever solver
                # model inserted its key first. Equal-cost ties retain order.
                if current is None or entry.body_literals < current.body_literals:
                    unique[entry.text] = entry
        if pack:
            for text, entry in unique.items():
                if entry.recipes is not None:
                    packed = entry.recipes.pack(entry.syntax)
                    if packed is not entry.syntax:
                        unique[text] = replace(entry, syntax=packed)
        self.entries = tuple(unique[text] for text in sorted(unique))
        self.clauses = tuple(entry.text for entry in self.entries)
        unique.clear()

    @property
    def statements(self):
        """Materialize native syntax only when a caller requests every rule."""
        return tuple(entry.statement for entry in self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    def __bool__(self) -> bool:
        return bool(self.entries)
