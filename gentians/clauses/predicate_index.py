from collections.abc import Iterable
from functools import lru_cache

from ..language.asp import Predicate


class PredicateIndex:
    def __init__(self, predicates: Iterable[Predicate]) -> None:
        self.predicates = tuple(sorted(set(predicates)))
        self.ids = {predicate: index for index, predicate in enumerate(self.predicates)}
        self.members = lru_cache(maxsize=8192)(self._members)

    def mask(self, predicates: Iterable[Predicate]) -> int:
        result = 0
        for predicate in predicates:
            index = self.ids.get(predicate)
            if index is not None:
                result |= 1 << index
        return result

    def _members(self, mask: int) -> frozenset[Predicate]:
        values = []
        while mask:
            bit = mask & -mask
            values.append(self.predicates[bit.bit_length() - 1])
            mask ^= bit
        return frozenset(values)


