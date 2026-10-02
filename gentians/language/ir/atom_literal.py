from collections.abc import Iterator
from dataclasses import dataclass

from clingo import ast

from ..asp import Predicate
from ..ast_nodes import literal
from .atom_template import AtomTemplate


@dataclass(frozen=True, slots=True)
class AtomLiteral:
    atom: AtomTemplate
    default_negated: bool = False
    double_negated: bool = False

    def __post_init__(self) -> None:
        if self.double_negated and not self.default_negated:
            raise ValueError("double negation requires default negation")

    @property
    def kind(self) -> str:
        return "normal"

    @property
    def arguments(self) -> tuple[ast.AST, ...]:
        return self.atom.binding_terms

    @property
    def dependencies(self) -> frozenset[Predicate]:
        return frozenset((self.atom.signature,))

    def concretizations(self, constants: dict[str, tuple[ast.AST, ...]]) -> Iterator["AtomLiteral"]:
        return (
            self if atom is self.atom
            else AtomLiteral(atom, self.default_negated, self.double_negated)
            for atom in self.atom.concretizations(constants)
        )

    def with_arguments(self, arguments: Iterator[ast.AST]) -> "AtomLiteral":
        atom = self.atom.with_arguments(arguments)
        return self if atom is self.atom else AtomLiteral(atom, self.default_negated, self.double_negated)

    def instantiate(self, variables: Iterator[ast.AST]) -> ast.AST:
        return literal(self.atom.instantiate(variables), self.default_negated, self.double_negated)
