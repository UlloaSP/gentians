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


def canonicalize_clauses(
    clauses: list[ReifiedClause],
    modes: dict[int, ClauseMode],
    max_variables: int,
) -> list[Clause]:
    representatives: dict[ArithmeticSystemKey, tuple[str, ast.AST, ReifiedClause]] = {}
    systems_cache: _ArithmeticSystemsCache = {}
    # A space has few distinct heads and many bodies per head.
    heads: dict[tuple[ReifiedLiteral, ...], ast.AST] = {}
    for clause in clauses:
        canonical = canonical_arithmetic_clause(
            clause, modes, max_variables, systems_cache
        )
        if canonical is None:
            continue
        key = canonical.key
        current = representatives.get(key)
        if current is None:
            statement = canonical.instantiate(modes, heads)
            representatives[key] = str(statement), statement, clause
        elif len(clause.body) > len(current[2].body):
            continue
        elif all(
            isinstance(relation, LinearConstraint)
            for system in canonical.systems
            for relation in system.relations
        ):
            if len(clause.body) < len(current[2].body):
                representatives[key] = current[0], current[1], clause
        else:
            statement = canonical.instantiate(modes, heads)
            rendered = str(statement)
            if (len(clause.body), rendered) < (
                len(current[2].body),
                current[0],
            ):
                representatives[key] = rendered, statement, clause

    ordered = sorted(
        representatives.values(), key=lambda representative: representative[0]
    )
    return [
        _clause_from_reified(rendered, statement, clause, modes)
        for rendered, statement, clause in ordered
    ]


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
