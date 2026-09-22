from clingo import ast

from ...language.asp import Predicate, parse_program
from ...language.ir.atom_literal import AtomLiteral
from ...language.ir.conditional_literal import ConditionalLiteral
from ..clause import Clause
from ..clause_mode import ClauseMode
from ..reified_clause import ReifiedClause
from .arithmetic import canonical_arithmetic_clause
from .arithmetic_system import ArithmeticSystemKey
from .linear_constraint import LinearConstraint


def canonicalize_clauses(
    clauses: list[ReifiedClause],
    modes: dict[int, ClauseMode],
    max_variables: int,
) -> list[Clause]:
    representatives: dict[ArithmeticSystemKey, tuple[str, ReifiedClause]] = {}
    for clause in clauses:
        canonical = canonical_arithmetic_clause(clause, modes, max_variables)
        if canonical is None:
            continue
        key = canonical.key
        current = representatives.get(key)
        if current is None:
            representatives[key] = canonical.render(modes), clause
        elif len(clause.body) > len(current[1].body):
            continue
        elif all(
            isinstance(relation, LinearConstraint)
            for system in canonical.systems
            for relation in system.relations
        ):
            if len(clause.body) < len(current[1].body):
                representatives[key] = current[0], clause
        else:
            rendered = canonical.render(modes)
            if (len(clause.body), rendered) < (
                len(current[1].body),
                current[0],
            ):
                representatives[key] = rendered, clause

    ordered = sorted(
        representatives.values(), key=lambda representative: representative[0]
    )
    statements = parse_program("\n".join(rendered for rendered, _clause in ordered))
    return [
        _clause_from_reified(rendered, statement, clause, modes)
        for statement, (rendered, clause) in zip(statements, ordered, strict=True)
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
            heads.add(mode.literal.atom.signature)
        elif isinstance(mode.literal, ConditionalLiteral):
            heads.add(mode.literal.conclusion.atom.signature)
            deps.update(
                predicate
                for condition in mode.literal.conditions
                for predicate in condition.dependencies
            )
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
