"""Nominal compatibility only for property maps with direct positive consumers.

Unary/order/key property bridges are deliberately retained. Filtering these
maps cannot suppress facts needed to derive some other property in ASP.
"""

from ..language import terms
from ..language.asp import Predicate
from ..language.ir.atom_literal import AtomLiteral
from .clause_mode import ClauseMode


class PropertyMaps:
    def __init__(self, modes: list[ClauseMode]):
        self.types: dict[Predicate, list[tuple[str, ...] | None]] = {}
        for mode in modes:
            if mode.section != "body" or not mode.positive_atom or not isinstance(mode.literal, AtomLiteral):
                continue
            atom = mode.literal.atom
            value = (tuple(binding.type for binding in mode.bindings)
                     if not atom.alternatives and all(terms.kind(term) == "variable" for term in atom.terms)
                     else None)
            self.types.setdefault(atom.signature, []).append(value)

    def compatible(self, left: Predicate, right: Predicate,
                   projection: tuple[tuple[int, int], ...]) -> bool:
        return any(ltypes is None or rtypes is None or all(
            ltypes[lpos] == "any" or rtypes[rpos] == "any" or ltypes[lpos] == rtypes[rpos]
            for lpos, rpos in projection)
            for ltypes in self.types.get(left, ()) for rtypes in self.types.get(right, ()))

    def tuple_mutex(self, left: Predicate, right: Predicate, projection: tuple[int, ...]) -> bool:
        return self.compatible(left, right, tuple((source, target) for target, source in enumerate(projection)))
