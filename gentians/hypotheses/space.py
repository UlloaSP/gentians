from collections.abc import Iterable

from clingo import ast

from ..clauses import Clause, ClauseSpace
from ..language.asp import Predicate, clause_predicates
from ..language.ir.inductive_task import InductiveTask


def prepare_space(task: InductiveTask, space: ClauseSpace) -> ClauseSpace:
    return ClauseSpace(_prune_uncloseable_clauses(space.entries, task_providers(task)))


def task_providers(task: InductiveTask) -> set[Predicate]:
    """Predicates the task can make true without a learned clause.

    A predicate defined only by one example context still closes a dependency:
    it is not always false. Coverage keeps every context isolated, so no
    context supplies atoms to another example.
    """
    return defined_predicates(
        (
            *task.background,
            *(
                statement
                for example in (*task.positive_examples, *task.negative_examples)
                for statement in example.context
            ),
        )
    )


def defined_predicates(statements: Iterable[ast.AST]) -> set[Predicate]:
    defined: set[Predicate] = set()
    for statement in statements:
        heads, _deps, _body = clause_predicates(statement)
        defined.update(heads)
    return defined


def _prune_uncloseable_clauses(
    entries: tuple[Clause, ...], task_defined: set[Predicate]
) -> list[Clause]:
    kept = list(entries)
    while True:
        providers = set(task_defined)
        for entry in kept:
            providers.update(entry.heads)
        filtered = [
            entry
            for entry in kept
            if entry.deps <= providers
        ]
        if len(filtered) == len(kept):
            return kept
        kept = filtered
