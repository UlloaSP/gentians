from collections.abc import Iterator
from dataclasses import dataclass
from itertools import product

from .atom_template import AtomTemplate
from .term_template import TermTemplate


@dataclass(frozen=True, slots=True)
class AggregateElement:
    terms: tuple[TermTemplate, ...]
    conditions: tuple[AtomTemplate, ...]

    @property
    def arguments(self) -> tuple[TermTemplate, ...]:
        return (*self.terms, *(term for atom in self.conditions for term in atom.terms))

    def concretizations(
        self, constants: dict[str, tuple[str, ...]]
    ) -> tuple["AggregateElement", ...]:
        return tuple(
            AggregateElement(terms, conditions)
            for terms in product(*(term.concretizations(constants) for term in self.terms))
            for conditions in product(
                *(atom.concretizations(constants) for atom in self.conditions)
            )
        )

    def render(self, variables: Iterator[str]) -> str:
        terms = ",".join(term.render(variables) for term in self.terms)
        conditions = ",".join(atom.render(variables) for atom in self.conditions)
        return f"{terms}:{conditions}" if conditions else terms
