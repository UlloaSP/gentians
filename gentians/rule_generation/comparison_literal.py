from collections.abc import Iterator
from dataclasses import dataclass

from .parser import Predicate
from .term_template import TermTemplate


@dataclass(frozen=True, slots=True)
class ComparisonLiteral:
    operator: str
    terms: tuple[TermTemplate, TermTemplate]
    family: bool = True

    @property
    def canonicalizable(self) -> bool:
        return self.family and self.operator != "=" and all(
            term.kind == "variable" for term in self.terms
        )

    @property
    def simple(self) -> bool:
        return self.family and all(term.kind == "variable" for term in self.terms)

    @property
    def kind(self) -> str:
        return "comparison"

    @property
    def arguments(self) -> tuple[TermTemplate, ...]:
        return self.terms

    @property
    def dependencies(self) -> frozenset[Predicate]:
        return frozenset()

    def render(self, variables: Iterator[str]) -> str:
        left, right = (term.render(variables) for term in self.terms)
        return f"{left}{self.operator}{right}"
