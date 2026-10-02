from collections import OrderedDict
from collections.abc import Set

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
    frozenset[int],
    frozenset[int],
    frozenset[int],
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
    external: set[int] = set()
    safe: set[int] = set()
    numeric: set[int] = set()
    for literal in clause.head:
        traits = modes[literal.mode_id]
        external.update(literal.variables)
        if traits.numeric_builtin:
            numeric.update(literal.variables)
        elif traits.numeric_positions:
            numeric.update(literal.variables[position] for position in traits.numeric_positions)
    for literal, traits in zip(clause.body, body_traits, strict=True):
        if traits.builtin:
            builtin.append(literal)
        else:
            non_builtin.append(literal)
            external.update(literal.variables)
        if traits.positive_atom:
            safe.update(literal.variables)
        if traits.output_guard:
            safe.add(literal.variables[-1])
        if traits.numeric_builtin:
            numeric.update(literal.variables)
        elif traits.numeric_positions:
            numeric.update(literal.variables[position] for position in traits.numeric_positions)

    # Non-builtins affect arithmetic only through these variable sets. Their
    # literal identities remain in CanonicalArithmeticClause and its final key.
    context_key: _ArithmeticContextKey = (
        tuple((literal.mode_id, literal.variables) for literal in builtin),
        frozenset(external),
        frozenset(safe),
        frozenset(numeric),
    )
    if systems_cache is not None and context_key in systems_cache:
        systems = systems_cache[context_key]
    else:
        systems = _canonical_systems(
            tuple(builtin),
            modes,
            context_key[1],
            context_key[2],
            context_key[3],
            max_variables,
        )
        if systems_cache is not None:
            if len(systems_cache) >= MAX_CACHED_SYSTEMS:
                systems_cache.popitem(last=False)
            systems_cache[context_key] = systems
    if systems is None:
        return None
    return CanonicalArithmeticClause(clause.head, tuple(non_builtin), systems)


def _canonical_systems(
    builtin: tuple[ReifiedLiteral, ...],
    modes: dict[int, ClauseMode],
    external: frozenset[int],
    safe: frozenset[int],
    numeric_variables: frozenset[int],
    max_variables: int,
) -> tuple[ArithmeticSystem, ...] | None:
    parent = list(range(max_variables))

    def find(variable: int) -> int:
        while parent[variable] != variable:
            parent[variable] = parent[parent[variable]]
            variable = parent[variable]
        return variable

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for literal in builtin:
        for variable in literal.variables[1:]:
            union(literal.variables[0], variable)

    components: dict[int, list[ReifiedLiteral]] = {}
    for literal in builtin:
        components.setdefault(find(literal.variables[0]), []).append(literal)

    systems: list[ArithmeticSystem] = []
    for literals in components.values():
        numeric_component = any(
            modes[literal.mode_id].numeric_builtin
            or set(literal.variables) <= numeric_variables
            for literal in literals
        )
        if not numeric_component:
            systems.append(_structural_system(literals, modes, safe))
            continue
        if any(
            not _is_linear(
                modes[literal.mode_id],
                set(literal.variables) <= numeric_variables,
            )
            for literal in literals
        ):
            system = _expression_system(
                literals, modes, external, safe, numeric_variables
            )
            systems.append(
                system
                if system is not None
                else _structural_system(literals, modes, safe)
            )
            continue
        constraints = tuple(
            _constraint(literal.variables, modes[literal.mode_id], max_variables)
            for literal in literals
        )
        component_variables = set().union(
            *(constraint.variables for constraint in constraints)
        )
        if not component_variables & external:
            systems.append(_structural_system(literals, modes, safe))
            continue
        normalized = _normalize_component(
            constraints,
            frozenset(component_variables - external),
            max_variables,
        )
        if normalized is None:
            return None
        oriented = _orient_linear_constraints(normalized, safe)
        if oriented is None:
            systems.append(_structural_system(literals, modes, safe))
            continue
        if oriented:
            systems.append(ArithmeticSystem(oriented))

    return tuple(sorted(systems, key=lambda system: repr(system.key)))


def _literal_key(literal: ReifiedLiteral) -> tuple[int, tuple[int, ...]]:
    return literal.mode_id, literal.variables


def _structural_system(
    literals: list[ReifiedLiteral], modes: dict[int, ClauseMode], safe: Set[int],
) -> ArithmeticSystem:
    return ArithmeticSystem(
        tuple(
            _arithmetic_relation(literal, modes, safe)
            for literal in sorted(literals, key=_literal_key)
        )
    )
