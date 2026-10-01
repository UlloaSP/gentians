from collections.abc import Iterator

from clingo import ast

from ...language.asp import Predicate
from ...language.ir.atom_literal import AtomLiteral
from ...language.ir.conditional_literal import ConditionalLiteral
from ...language.ir.head_aggregate_element import HeadAggregateElement
from ..clause import Clause
from ..clause_mode import ClauseMode
from ..reified_clause import ReifiedClause
from ..reified_literal import ReifiedLiteral
from .arithmetic import _ArithmeticSystemsCache, canonical_arithmetic_clause
from .arithmetic_system import ArithmeticSystemKey
from .linear_constraint import LinearConstraint


class ClauseCanonicalizer:
    """Retain the globally preferred representative of each canonical rule."""

    def __init__(self, modes: dict[int, ClauseMode], max_variables: int) -> None:
        self.modes = modes
        self.max_variables = max_variables
        self.representatives: dict[ArithmeticSystemKey, tuple[str, ast.AST, ReifiedClause]] = {}
        self.systems_cache = _ArithmeticSystemsCache()
        # A space has few distinct heads and many bodies per head.
        self.heads: dict[tuple[ReifiedLiteral, ...], ast.AST] = {}

    def add(self, clause: ReifiedClause) -> None:
        canonical = canonical_arithmetic_clause(
            clause, self.modes, self.max_variables, self.systems_cache
        )
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
        for rendered, statement, clause in self.representatives.values():
            yield _clause_from_reified(rendered, statement, clause, self.modes)


def _clause_from_reified(
    rendered: str,
    statement: ast.AST,
    clause: ReifiedClause,
    modes: dict[int, ClauseMode],
) -> Clause:
    heads: set[Predicate] = set()
    deps: set[Predicate] = set()
    for literal in clause.head:
        mode = modes[literal.mode_id]
        if isinstance(mode.literal, AtomLiteral):
            if mode.literal.default_negated:
                deps.add(mode.literal.atom.signature)
            else:
                heads.add(mode.literal.atom.signature)
        elif isinstance(mode.literal, ConditionalLiteral):
            if isinstance(mode.literal.conclusion, AtomLiteral):
                if mode.literal.conclusion.default_negated:
                    deps.add(mode.literal.conclusion.atom.signature)
                else:
                    heads.add(mode.literal.conclusion.atom.signature)
            deps.update(
                predicate
                for condition in mode.literal.conditions
                for predicate in condition.dependencies
            )
        elif isinstance(mode.literal, HeadAggregateElement):
            if isinstance(mode.literal.conclusion, AtomLiteral):
                if mode.literal.conclusion.default_negated:
                    deps.add(mode.literal.conclusion.atom.signature)
                else:
                    heads.add(mode.literal.conclusion.atom.signature)
            deps.update(mode.literal.dependencies)
    for literal in clause.body:
        mode = modes[literal.mode_id]
        deps.update(mode.dependencies)
    body_literals = len(clause.body) + sum(
        modes[literal.mode_id].condition_count
        for literal in (*clause.head, *clause.body)
    )
    return Clause(
        rendered,
        statement,
        frozenset(heads),
        frozenset(deps),
        body_literals,
    )
