import time
from collections.abc import Callable, Iterable
from functools import wraps

from clingo import ast

from ..language.asp import Predicate, clause_predicates
from ..language.ir.inductive_task import InductiveTask
from ..clauses import Clause, ClauseSpace
from ..timing import add, current_phase


def record_generation_time(method: Callable) -> Callable:
    @wraps(method)
    def measured(*args, **kwargs):
        started = time.perf_counter()
        result = method(*args, **kwargs)
        # Benchmark schema keeps "closure" as the invariant-work time category.
        add(f"{current_phase()}.closure", time.perf_counter() - started)
        return result

    return measured


def prepare_space(task: InductiveTask, space: ClauseSpace) -> ClauseSpace:
    background = defined_predicates(task.background)
    entries = prune_uncloseable_clauses(space.entries, background)
    return ClauseSpace(entries)


def defined_predicates(statements: Iterable[ast.AST]) -> set[Predicate]:
    defined: set[Predicate] = set()
    for statement in statements:
        heads, _deps, _body = clause_predicates(statement)
        defined.update(heads)
    return defined


def prune_uncloseable_clauses(
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


def bits(mask: int):
    while mask:
        bit = mask & -mask
        yield bit
        mask ^= bit
