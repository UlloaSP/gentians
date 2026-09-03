from collections.abc import Iterator
from dataclasses import dataclass

from .atom_template import AtomTemplate
from ..asp import Predicate
from .term_template import TermTemplate


@dataclass(frozen=True, slots=True)
class AggregateLiteral:
    function: str
    tuple_terms: tuple[TermTemplate, ...]
    conditions: tuple[AtomTemplate, ...]
    result: TermTemplate

    @property
    def kind(self) -> str:
        return "aggregate"

    @property
    def arguments(self) -> tuple[TermTemplate, ...]:
        return (
            *self.tuple_terms,
            *(term for atom in self.conditions for term in atom.terms),
            self.result,
        )

    @property
    def dependencies(self) -> frozenset[Predicate]:
        return frozenset(atom.signature for atom in self.conditions)

    def render(self, variables: Iterator[str]) -> str:
        tuple_values = tuple(term.render(variables) for term in self.tuple_terms)
        conditions = tuple(atom.render(variables) for atom in self.conditions)
        result = self.result.render(variables)
        return (
            f"#{self.function}"
            + "{"
            + ",".join(tuple_values)
            + ":"
            + ",".join(conditions)
            + "}="
            + result
        )
