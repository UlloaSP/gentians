"""Immutable metadata using signed predicate masks."""

from collections.abc import Iterable
from dataclasses import dataclass

from ..language.asp import Predicate
from .predicate_index import PredicateIndex


@dataclass(frozen=True, slots=True, eq=False)
class ClauseMetadata:
    head_mask: int
    dep_mask: int
    body_literals: int
    index: PredicateIndex

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ClauseMetadata):
            return NotImplemented
        if self.body_literals != other.body_literals:
            return False
        if self.index is other.index:
            return (self.head_mask, self.dep_mask) == (other.head_mask, other.dep_mask)
        return (self.index.members(self.head_mask) == other.index.members(other.head_mask)
                and self.index.members(self.dep_mask) == other.index.members(other.dep_mask))

    def __hash__(self) -> int:
        return hash((self.index.members(self.head_mask), self.index.members(self.dep_mask), self.body_literals))

    @classmethod
    def from_predicates(
        cls, heads: Iterable[Predicate], deps: Iterable[Predicate], body_literals: int,
    ) -> "ClauseMetadata":
        heads, deps = tuple(heads), tuple(deps)
        index = PredicateIndex((*heads, *deps))
        return cls(index.mask(heads), index.mask(deps), body_literals, index)


