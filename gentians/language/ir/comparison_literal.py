from collections.abc import Iterator
from dataclasses import dataclass, field

from ..asp import Predicate
from .term_template import TermTemplate


@dataclass(frozen=True, slots=True)
class ComparisonLiteral:
    terms: tuple[TermTemplate, ...]
    operators: tuple[str, ...]
    default_negated: bool = False
    fully_implicit_directions: bool = field(default=False, repr=False)
    double_negated: bool = False

    def __post_init__(self) -> None:
        if len(self.terms) != len(self.operators) + 1:
            raise ValueError("a comparison requires one more term than operators")
        if not self.operators:
            raise ValueError("a comparison requires at least one operator")
        if self.double_negated and not self.default_negated:
            raise ValueError("double negation requires default negation")

    @property
    def canonicalizable(self) -> bool:
        return (
            not self.default_negated
            and len(self.operators) == 1
            and self.operators[0] != "="
            and all(term.kind == "variable" for term in self.terms)
        )

    @property
    def simple(self) -> bool:
        return (
            not self.default_negated
            and len(self.operators) == 1
            and all(term.kind == "variable" for term in self.terms)
        )

    @property
    def arithmetic(self) -> bool:
        return any(term.contains_arithmetic for term in self.terms)

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
        rendered = self.terms[0].render(variables)
        if self.terms[0].kind == "pool":
            rendered = f"({rendered})"
        for operator, term in zip(self.operators, self.terms[1:], strict=True):
            value = term.render(variables)
            rendered += operator + (f"({value})" if term.kind == "pool" else value)
        if self.double_negated:
            return f"not not {rendered}"
        return f"not {rendered}" if self.default_negated else rendered
