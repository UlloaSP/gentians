from collections.abc import Iterable

from clingo import ast

from ..clauses import Clause, ClauseSpace
from ..language.asp import Predicate, clause_predicates
from ..language.ir.inductive_task import InductiveTask


def prepare_space(task: InductiveTask, space: ClauseSpace) -> ClauseSpace:
    background = defined_predicates(task.background)
    return ClauseSpace(_prune_uncloseable_clauses(space.entries, background))


def defined_predicates(statements: Iterable[ast.AST]) -> set[Predicate]:
    defined: set[Predicate] = set()
    for statement in statements:
        heads, _deps, _body = clause_predicates(statement)
        defined.update(heads)
    return defined


def _prune_uncloseable_clauses(
    entries: tuple[Clause, ...], background: set[Predicate]
) -> list[Clause]:
    kept = list(entries)
    while True:
        providers = set(background)
        for entry in kept:
            providers.update(entry.heads)
        invalid_bundles = {
            entry.bundle
            for entry in kept
            if entry.bundle is not None and not entry.deps <= providers
        }
        filtered = [
            entry
            for entry in kept
            if entry.deps <= providers and entry.bundle not in invalid_bundles
        ]
        if len(filtered) == len(kept):
            return kept
        kept = filtered
