from collections.abc import Iterator
from functools import lru_cache

from clingo import ast

from ...language.asp import Predicate
from ..clause import Clause
from ..clause_mode import ClauseMode
from ..reified_clause import ReifiedClause
from ..reified_literal import ReifiedLiteral
from .arithmetic import _ArithmeticSystemsCache, canonical_arithmetic_clause
from .arithmetic_system import ArithmeticSystemKey
from .canonical_clause import CanonicalArithmeticClause
from .linear_constraint import LinearConstraint


class ClauseCanonicalizer:
    """Retain the globally preferred representative of each canonical rule."""

    def __init__(self, modes: dict[int, ClauseMode], max_variables: int) -> None:
        self.modes = modes
        self.max_variables = max_variables
        self.representatives: dict[ArithmeticSystemKey, tuple[str, ast.AST, ReifiedClause]] = {}
        self.systems_cache = _ArithmeticSystemsCache()
        self.has_builtins = any(mode.section == "body" and mode.builtin for mode in modes.values())
        # A space has few distinct heads and many bodies per head.
        self.heads: dict[tuple[ReifiedLiteral, ...], ast.AST] = {}

    def add(self, clause: ReifiedClause) -> None:
        canonical = canonical_arithmetic_clause(
            clause, self.modes, self.max_variables, self.systems_cache
        ) if self.has_builtins else CanonicalArithmeticClause(clause.head, clause.body, ())
        if canonical is None:
            return
        key = canonical.key
        current = self.representatives.get(key)
        if current is None:
            statement = canonical.instantiate(self.modes, self.heads)
            self.representatives[key] = str(statement), statement, clause
        elif len(clause.body) > len(current[2].body):
            return
        elif all(
            isinstance(relation, LinearConstraint)
            for system in canonical.systems
            for relation in system.relations
        ):
            if len(clause.body) < len(current[2].body):
                self.representatives[key] = current[0], current[1], clause
        else:
            statement = canonical.instantiate(self.modes, self.heads)
            rendered = str(statement)
            if (len(clause.body), rendered) < (
                len(current[2].body),
                current[0],
            ):
                self.representatives[key] = rendered, statement, clause

    def finish(self) -> Iterator[Clause]:
        # ClauseSpace owns final text deduplication and deterministic ordering.
        modes = self.modes

        @lru_cache(maxsize=8192)
        def metadata(head: tuple[int, ...], body: tuple[int, ...]):
            return _clause_metadata(head, body, modes)

        for rendered, statement, clause in self.representatives.values():
            yield Clause(rendered, statement, *metadata(
                tuple(literal.mode_id for literal in clause.head),
                tuple(literal.mode_id for literal in clause.body),
            ))


def _clause_metadata(
    head: tuple[int, ...],
    body: tuple[int, ...],
    modes: dict[int, ClauseMode],
) -> tuple[frozenset[Predicate], frozenset[Predicate], int]:
    """Providers, dependencies and body cost depend on modes, not bindings."""
    heads: set[Predicate] = set()
    deps: set[Predicate] = set()
    body_literals = len(body)
    for mode_id in head:
        mode = modes[mode_id]
        heads.update(mode.head_predicates)
        deps.update(mode.head_dependencies)
        body_literals += mode.condition_count
    for mode_id in body:
        mode = modes[mode_id]
        deps.update(mode.dependencies)
        body_literals += mode.condition_count
    return frozenset(heads), frozenset(deps), body_literals
