from dataclasses import dataclass, field

from clingo import ast

from ..language.asp import Predicate


@dataclass(frozen=True, slots=True)
class Clause:
    text: str
    statement: ast.AST = field(compare=False, repr=False)
    heads: frozenset[Predicate]
    deps: frozenset[Predicate]
    body_literals: int
    bundle: int | None = None
