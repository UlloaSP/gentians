from dataclasses import dataclass

from .parser import Predicate


@dataclass(frozen=True, slots=True)
class AggregateDeclaration:
    recall: int
    function: str
    atoms: tuple[Predicate, ...]
    unbalanced: bool
