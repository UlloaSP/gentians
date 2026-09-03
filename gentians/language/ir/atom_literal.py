from collections.abc import Iterator
from dataclasses import dataclass

from .atom_template import AtomTemplate
from ..asp import Predicate
from .term_template import TermTemplate


@dataclass(frozen=True, slots=True)
class AtomLiteral:
    atom: AtomTemplate
    default_negated: bool = False

    @property
    def kind(self) -> str:
        return "normal"

    @property
    def arguments(self) -> tuple[TermTemplate, ...]:
        return self.atom.terms

    @property
    def dependencies(self) -> frozenset[Predicate]:
        return frozenset((self.atom.signature,))

    def render(self, variables: Iterator[str]) -> str:
        atom = self.atom.render(variables)
        return f"not {atom}" if self.default_negated else atom
