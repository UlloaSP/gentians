import re
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import product

from ..asp import Predicate, signed_predicate
from .term_binding import TermBinding
from .term_template import TermTemplate


@dataclass(frozen=True, slots=True)
class AtomTemplate:
    name: str
    terms: tuple[TermTemplate, ...]
    strong: bool = False
    alternatives: tuple[tuple[TermTemplate, ...], ...] = ()

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z_][A-Za-z0-9_']*", self.name):
            raise ValueError(f"invalid mode predicate: {self.name}")
        if self.alternatives and (
            len(self.alternatives) < 2
            or self.alternatives[0] != self.terms
            or any(len(terms) != len(self.terms) for terms in self.alternatives)
        ):
            raise ValueError("pooled atoms require alternatives of the same arity")

    @property
    def binding_terms(self) -> tuple[TermTemplate, ...]:
        return tuple(
            term for alternative in self.alternatives for term in alternative
        ) if self.alternatives else self.terms

    @property
    def signature(self) -> Predicate:
        return signed_predicate(self.name, len(self.terms), self.strong)

    @property
    def unsigned_signature(self) -> Predicate:
        return self.name, len(self.terms)

    def bindings(self) -> tuple[TermBinding, ...]:
        return tuple(
            binding
            for index, term in enumerate(self.binding_terms)
            for binding in term.bindings((index,))
        )

    def concretizations(
        self, constants: dict[str, tuple[str, ...]]
    ) -> tuple["AtomTemplate", ...]:
        if self.alternatives:
            choices = tuple(
                tuple(product(*(term.concretizations(constants) for term in alternative)))
                for alternative in self.alternatives
            )
            return tuple(
                AtomTemplate(self.name, concrete[0], self.strong, concrete)
                for concrete in product(*choices)
            )
        return (
            tuple(
                AtomTemplate(self.name, terms, self.strong)
                for terms in product(
                    *(term.concretizations(constants) for term in self.terms)
                )
            )
            if self.terms
            else (self,)
        )

    def render(self, variables: Iterator[str]) -> str:
        if self.alternatives:
            arguments = ";".join(
                ",".join(term.render(variables) for term in alternative)
                for alternative in self.alternatives
            )
            atom = f"{self.name}({arguments})"
        else:
            arguments = tuple(term.render(variables) for term in self.terms)
            atom = f"{self.name}({','.join(arguments)})" if arguments else self.name
        return f"-{atom}" if self.strong else atom
