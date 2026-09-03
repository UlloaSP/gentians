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

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z][A-Za-z0-9_]*", self.name):
            raise ValueError(f"invalid mode predicate: {self.name}")

    @property
    def signature(self) -> Predicate:
        return signed_predicate(self.name, len(self.terms), self.strong)

    @property
    def unsigned_signature(self) -> Predicate:
        return self.name, len(self.terms)

    def bindings(self) -> tuple[TermBinding, ...]:
        return tuple(
            binding
            for index, term in enumerate(self.terms)
            for binding in term.bindings((index,))
        )

    def concretizations(
        self, constants: dict[str, tuple[str, ...]]
    ) -> tuple["AtomTemplate", ...]:
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
        arguments = tuple(term.render(variables) for term in self.terms)
        atom = f"{self.name}({','.join(arguments)})" if arguments else self.name
        return f"-{atom}" if self.strong else atom
