from ...language.ir.aggregate_literal import AggregateLiteral
from ...language.ir.arithmetic_literal import ArithmeticLiteral
from ...language.ir.atom_literal import AtomLiteral
from ...language.ir.comparison_literal import ComparisonLiteral
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


def _is_builtin(mode: ClauseMode) -> bool:
    return isinstance(mode.literal, ArithmeticLiteral) or (
        isinstance(mode.literal, ComparisonLiteral)
        and not mode.literal.default_negated
        and bool(mode.bindings)
        and (
            mode.literal.canonicalizable
            or mode.literal.arithmetic
            or all(binding.type == "numeric" for binding in mode.bindings)
        )
    )


def _is_positive_atom(mode: ClauseMode) -> bool:
    return isinstance(mode.literal, AtomLiteral) and not mode.literal.default_negated


def _is_numeric_builtin(mode: ClauseMode) -> bool:
    return isinstance(mode.literal, ArithmeticLiteral) or (
        isinstance(mode.literal, ComparisonLiteral)
        and (
            mode.literal.arithmetic
            or all(binding.type == "numeric" for binding in mode.bindings)
        )
    )


def canonical_arithmetic_clause(
    clause: ReifiedClause,
    modes: dict[int, ClauseMode],
    max_variables: int,
) -> CanonicalArithmeticClause | None:
    builtin = [
        literal for literal in clause.body if _is_builtin(modes[literal.mode_id])
    ]
    non_builtin = tuple(
        literal for literal in clause.body if not _is_builtin(modes[literal.mode_id])
    )
    if not builtin:
        return CanonicalArithmeticClause(clause.head, non_builtin, ())

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

    external = {
        variable
        for literal in (*clause.head, *clause.body)
        if not _is_builtin(modes[literal.mode_id])
        for variable in literal.variables
    }
    external.update(
        variable for literal in clause.head for variable in literal.variables
    )
    safe = {
        variable
        for literal in clause.body
        if _is_positive_atom(modes[literal.mode_id])
        for variable in literal.variables
    }
    safe.update(
        literal.variables[-1]
        for literal in clause.body
        if isinstance(modes[literal.mode_id].literal, AggregateLiteral)
    )
    numeric_variables = _numeric_variables(clause, modes)

    components: dict[int, list[ReifiedLiteral]] = {}
    for literal in builtin:
        components.setdefault(find(literal.variables[0]), []).append(literal)

    systems: list[ArithmeticSystem] = []
    for literals in components.values():
        numeric_component = any(
            _is_numeric_builtin(modes[literal.mode_id])
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
            _constraint(literal, modes[literal.mode_id], max_variables)
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

    return CanonicalArithmeticClause(
        clause.head,
        non_builtin,
        tuple(sorted(systems, key=lambda system: repr(system.key))),
    )


def _literal_key(literal: ReifiedLiteral) -> tuple[int, tuple[int, ...]]:
    return literal.mode_id, literal.variables


def _numeric_variables(
    clause: ReifiedClause,
    modes: dict[int, ClauseMode],
) -> set[int]:
    numeric: set[int] = set()
    for literal in (*clause.head, *clause.body):
        mode = modes[literal.mode_id]
        if _is_numeric_builtin(mode):
            numeric.update(literal.variables)
        numeric.update(
            variable
            for variable, binding in zip(literal.variables, mode.bindings, strict=True)
            if binding.type == "numeric"
        )
    return numeric


def _structural_system(
    literals: list[ReifiedLiteral], modes: dict[int, ClauseMode], safe: set[int],
) -> ArithmeticSystem:
    return ArithmeticSystem(
        tuple(
            _arithmetic_relation(literal, modes, safe)
            for literal in sorted(literals, key=_literal_key)
        )
    )
