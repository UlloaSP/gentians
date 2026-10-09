"""Conservative nominal binding domains for modes with global flat variables."""

from ..language import terms
from ..language.ir.atom_literal import AtomLiteral
from .clause_mode import ClauseMode


def nominal_binding_facts(modes: list[ClauseMode]) -> list[str]:
    types = {binding.type for mode in modes for binding in mode.bindings}
    if len(types) < 2 or "any" in types:
        return []
    if any(not isinstance(mode.literal, AtomLiteral)
           or mode.literal.atom.alternatives or mode.guard_terms
           or any(terms.kind(term) != "variable" for term in mode.arguments)
           for mode in modes):
        # Scope-local names can reuse V0 with incompatible nominal types.
        return []
    return ["nominal_bindings.", *(f"binding_type({t})." for t in sorted(types))]


def connected_binding_facts(modes: list[ClauseMode]) -> list[str]:
    """Introduce typed global ids only at their actual first occurrence.

    Input/output closure remains declarative in legality/flow. Mode-id order
    need not be a valid execution order of the selected body literals.
    """
    if not modes or any(
        not isinstance(mode.literal, AtomLiteral) or mode.literal.atom.alternatives
        or mode.guard_terms or mode.condition_count
        or mode.section == "head" and (mode.head is None or mode.head.kind != "normal")
        or any(terms.kind(term) != "variable" for term in mode.arguments)
        or any(binding.type == "any" for binding in mode.bindings)
        for mode in modes
    ):
        return []
    return ["connected_bindings."]
