import re
from collections.abc import Iterator
from dataclasses import dataclass, field
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
    binding_terms: tuple[ast.AST, ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z_][A-Za-z0-9_']*", self.name):
            raise ValueError(f"invalid mode predicate: {self.name}")
        if self.alternatives and (
            len(self.alternatives) < 2
            or self.alternatives[0] != self.terms
            or any(len(terms) != len(self.terms) for terms in self.alternatives)
        ):
            raise ValueError("pooled atoms require alternatives of the same arity")
        object.__setattr__(
            self, "binding_terms",
            tuple(term for alternative in self.alternatives for term in alternative)
            if self.alternatives else self.terms,
        )

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
        self, constants: dict[str, tuple[ast.AST, ...]]
    ) -> Iterator["AtomTemplate"]:
        if not any(mode_terms.constant_types(term) for term in self.binding_terms):
            yield self
            return
        if self.alternatives:
            width = len(self.terms)
            for terms in product(*(mode_terms.concretizations(term, constants) for term in self.binding_terms)):
                concrete = tuple(
                    terms[index * width : (index + 1) * width]
                    for index in range(len(self.alternatives))
                )
                yield self if concrete == self.alternatives else AtomTemplate(self.name, concrete[0], self.strong, concrete)
        else:
            for terms in product(*(mode_terms.concretizations(term, constants) for term in self.terms)):
                yield self if terms == self.terms else AtomTemplate(self.name, terms, self.strong)

    def instantiate(self, variables: Iterator[ast.AST]) -> ast.AST:
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
