"""Optional binding domains that encode existing argument properties earlier."""

from ..language import terms
from ..language.ir.atom_literal import AtomLiteral
from .analysis.properties import ClosedWorldProperties
from .clause_mode import ClauseMode


def property_binding_facts(modes: list[ClauseMode], properties: ClosedWorldProperties) -> list[str]:
    parts = []
    for mode in modes:
        literal = mode.literal
        if (not isinstance(literal, AtomLiteral) or literal.atom.alternatives or mode.guard_terms
                or any(terms.kind(term) != "variable" for term in literal.atom.terms)):
            continue
        parts.append(f"binding_flat_mode({mode.id}).")
        if mode.section != "body" or not mode.positive_atom:
            continue
        roots = list(range(len(mode.bindings)))

        def root(arg):
            while roots[arg] != arg:
                arg = roots[arg]
            return arg

        for predicate, first, second in sorted(properties.arg_equal):
            if predicate != literal.atom.signature:
                continue
            left, right = mode.bindings[first], mode.bindings[second]
            if left.type != right.type or (left.label and right.label and left.label != right.label):
                continue
            a, b = sorted((root(first), root(second)))
            roots[b] = a
        for arg in range(len(roots)):
            original = root(arg)
            if original != arg:
                parts.append(f"binding_alias({mode.id},{arg},{original}).")
    return parts
