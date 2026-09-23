from collections.abc import Iterator
from dataclasses import dataclass
from itertools import product

from ..asp import Predicate
from .atom_template import AtomTemplate
from .term_template import TermTemplate


@dataclass(frozen=True, slots=True)
class HeadAggregateElement:
    terms: tuple[TermTemplate, ...]
    atom: AtomTemplate
    conditions: tuple[AtomTemplate, ...]

    @property
    def kind(self) -> str:
        return "head_aggregate"

    @property
    def arguments(self) -> tuple[TermTemplate, ...]:
        return (
            *self.terms,
            *self.atom.terms,
            *(term for condition in self.conditions for term in condition.terms),
        )

    @property
    def dependencies(self) -> frozenset[Predicate]:
        return frozenset(condition.signature for condition in self.conditions)

    def concretizations(
        self, constants: dict[str, tuple[str, ...]]
    ) -> tuple["HeadAggregateElement", ...]:
        return tuple(
            HeadAggregateElement(terms, atom, conditions)
            for terms in product(*(term.concretizations(constants) for term in self.terms))
            for atom in self.atom.concretizations(constants)
            for conditions in product(
                *(condition.concretizations(constants) for condition in self.conditions)
            )
        )

    def render(self, variables: Iterator[str]) -> str:
        terms = ",".join(term.render(variables) for term in self.terms)
        atom = self.atom.render(variables)
        conditions = ",".join(condition.render(variables) for condition in self.conditions)
        return f"{terms}:{atom}:{conditions}" if conditions else f"{terms}:{atom}"
