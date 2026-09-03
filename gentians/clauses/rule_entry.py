from dataclasses import dataclass

from ..language.asp import Predicate


@dataclass(frozen=True, slots=True)
class RuleEntry:
    text: str
    heads: frozenset[Predicate]
    deps: frozenset[Predicate]
    body_literals: int
    bundle: int | None = None
