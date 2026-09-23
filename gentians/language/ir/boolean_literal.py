from collections.abc import Iterator
from dataclasses import dataclass

from ..asp import Predicate
from .term_template import TermTemplate


@dataclass(frozen=True, slots=True)
class BooleanLiteral:
    value: bool
    default_negated: bool = False
    double_negated: bool = False

    def __post_init__(self) -> None:
        if self.double_negated and not self.default_negated:
            raise ValueError("double negation requires default negation")

    @property
    def kind(self) -> str:
        return "boolean"

    @property
    def arguments(self) -> tuple[TermTemplate, ...]:
        return ()

    @property
    def dependencies(self) -> frozenset[Predicate]:
        return frozenset()

    def render(self, variables: Iterator[str]) -> str:
        value = "#true" if self.value else "#false"
        if self.double_negated:
            return f"not not {value}"
        return f"not {value}" if self.default_negated else value
