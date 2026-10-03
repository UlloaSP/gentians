from collections import OrderedDict
from collections.abc import Set
from functools import lru_cache

from ..clause_mode import ClauseMode
from ..reified_clause import ReifiedClause
from ..reified_literal import ReifiedLiteral
from .arithmetic_system import ArithmeticSystem
from .canonical_clause import CanonicalArithmeticClause
from .expression_normalization import _arithmetic_relation, _expression_system
from .linear_normalization import (
    _constraint,
    _is_linear,
    _normalize_component,
    _orient_linear_constraints,
)

_ArithmeticContextKey = tuple[
    tuple[tuple[int, tuple[int, ...]], ...],
    int,
    int,
    int,
]
_ArithmeticSystemsCache = OrderedDict[
    _ArithmeticContextKey,
    tuple[ArithmeticSystem, ...] | None,
]

# Bound task-local reuse even when many raw encodings share one representative.
MAX_CACHED_SYSTEMS = 8192


def canonical_arithmetic_clause(
    clause: ReifiedClause,
    modes: dict[int, ClauseMode],
    max_variables: int,
    systems_cache: _ArithmeticSystemsCache | None = None,
) -> CanonicalArithmeticClause | None:
    """Canonicalize one clause, optionally reusing systems within one mode space."""
    body_traits = [modes[literal.mode_id] for literal in clause.body]
    if not any(traits.builtin for traits in body_traits):
        return CanonicalArithmeticClause(clause.head, clause.body, ())
    builtin: list[ReifiedLiteral] = []
    non_builtin: list[ReifiedLiteral] = []
    external = safe = numeric = 0
    for literal in clause.head:
        traits = modes[literal.mode_id]
        external |= literal.variable_mask
        if traits.numeric_builtin:
            numeric |= literal.variable_mask
        elif traits.numeric_positions:
            for position in traits.numeric_positions:
                numeric |= 1 << literal.variables[position]
    for literal, traits in zip(clause.body, body_traits, strict=True):
        if traits.builtin:
            builtin.append(literal)
        else:
            non_builtin.append(literal)
            external |= literal.variable_mask
        if traits.positive_atom:
            safe |= literal.variable_mask
        if traits.output_guard:
            safe |= 1 << literal.variables[-1]
        if traits.numeric_builtin:
            numeric |= literal.variable_mask
        elif traits.numeric_positions:
            for position in traits.numeric_positions:
                numeric |= 1 << literal.variables[position]

    # Non-builtins affect arithmetic only through these variable masks. Their
    # literal identities remain in CanonicalArithmeticClause and its final key.
    context_key: _ArithmeticContextKey = (
        tuple(literal.key for literal in builtin),
        external,
        safe,
        numeric,
    )
    if systems_cache is not None and context_key in systems_cache:
        systems = systems_cache[context_key]
    else:
        systems = _canonical_systems(
            tuple(builtin),
            modes,
            external,
            safe,
            numeric,
            max_variables,
        )
        if systems_cache is not None:
            if len(systems_cache) >= MAX_CACHED_SYSTEMS:
                systems_cache.popitem(last=False)
            systems_cache[context_key] = systems
    if systems is None:
        return None
    return CanonicalArithmeticClause(clause.head, tuple(non_builtin), systems)


def _variables(mask: int) -> frozenset[int]:
    return frozenset(variable for variable in range(mask.bit_length()) if mask & (1 << variable))


@lru_cache(maxsize=8192)
def _component_indices(masks: tuple[int, ...]) -> tuple[tuple[int, ...], ...]:
    """Partition literal indices by shared variables, preserving their order."""
    remaining = (1 << len(masks)) - 1
    components = []
    while remaining:
        first = (remaining & -remaining).bit_length() - 1
        connected = 1 << first
        variables = masks[first]
        remaining &= ~connected
        while True:
            before = connected
            for index, mask in enumerate(masks):
                bit = 1 << index
                if remaining & bit and variables & mask:
                    connected |= bit
                    variables |= mask
                    remaining &= ~bit
            if connected == before:
                break
        components.append(tuple(index for index in range(len(masks)) if connected & (1 << index)))
    return tuple(components)


def _canonical_systems(
    builtin: tuple[ReifiedLiteral, ...],
    modes: dict[int, ClauseMode],
    external: int,
    safe: int,
    numeric_variables: int,
    max_variables: int,
) -> tuple[ArithmeticSystem, ...] | None:
    systems: list[ArithmeticSystem] = []
    for indices in _component_indices(tuple(literal.variable_mask for literal in builtin)):
        literals = [builtin[index] for index in indices]
        numeric_component = any(
            modes[literal.mode_id].numeric_builtin
            or literal.variable_mask & numeric_variables == literal.variable_mask
            for literal in literals
        )
        if not numeric_component:
            systems.append(_structural_system(literals, modes, _variables(safe)))
            continue
        if any(
            not _is_linear(
                modes[literal.mode_id],
                literal.variable_mask & numeric_variables == literal.variable_mask,
            )
            for literal in literals
        ):
            system = _expression_system(
                literals, modes, _variables(external), _variables(safe), _variables(numeric_variables)
            )
            systems.append(
                system
                if system is not None
                else _structural_system(literals, modes, _variables(safe))
            )
            continue
        constraints = tuple(
            _constraint(literal.variables, modes[literal.mode_id], max_variables)
            for literal in literals
        )
        component_variables = 0
        for constraint in constraints:
            component_variables |= constraint.variable_mask
        if not component_variables & external:
            systems.append(_structural_system(literals, modes, _variables(safe)))
            continue
        normalized = _normalize_component(
            constraints,
            component_variables & ~external,
            max_variables,
        )
        if normalized is None:
            return None
        oriented = _orient_linear_constraints(normalized, safe)
        if oriented is None:
            systems.append(_structural_system(literals, modes, _variables(safe)))
            continue
        if oriented:
            systems.append(ArithmeticSystem(oriented))

    return tuple(sorted(systems, key=lambda system: repr(system.key)))


def _literal_key(literal: ReifiedLiteral) -> tuple[int, tuple[int, ...]]:
    return literal.key


def _structural_system(
    literals: list[ReifiedLiteral], modes: dict[int, ClauseMode], safe: Set[int],
) -> ArithmeticSystem:
    return ArithmeticSystem(
        tuple(
            _arithmetic_relation(literal, modes, safe)
            for literal in sorted(literals, key=_literal_key)
        )
    )
