import re
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import product

from clingo import ast

from .. import terms as mode_terms
from ..asp import Predicate, signed_predicate
from ..ast_nodes import LOCATION
from .term_binding import TermBinding


@dataclass(frozen=True, slots=True)
class AtomTemplate:
    name: str
    terms: tuple[ast.AST, ...]
    strong: bool = False
    alternatives: tuple[tuple[ast.AST, ...], ...] = ()

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
    def binding_terms(self) -> tuple[ast.AST, ...]:
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
            for binding in mode_terms.bindings(term, (index,))
        )

    def concretizations(
        self, constants: dict[str, tuple[str, ...]]
    ) -> tuple["AtomTemplate", ...]:
        if self.alternatives:
            choices = tuple(
                tuple(product(*(mode_terms.concretizations(term, constants) for term in alternative)))
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
                    *(mode_terms.concretizations(term, constants) for term in self.terms)
                )
            )
            if self.terms
            else (self,)
        )

    def instantiate(self, variables: Iterator[str]) -> ast.AST:
        groups = self.alternatives or (self.terms,)
        symbols = [
            ast.Function(LOCATION, self.name,
                         [mode_terms.instantiate(term, variables) for term in terms], False)
            for terms in groups
        ]
        symbol = ast.Pool(LOCATION, symbols) if self.alternatives else symbols[0]
        if self.strong:
            symbol = ast.UnaryOperation(LOCATION, ast.UnaryOperator.Minus, symbol)
        return ast.SymbolicAtom(symbol)
