from dataclasses import dataclass

from .parser import Predicate


@dataclass(frozen=True, slots=True)
class RuleEntry:
    text: str
    heads: frozenset[Predicate]
    deps: frozenset[Predicate]
    body_literals: int
