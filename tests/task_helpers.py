from typing import Any

from clingo import ast

from gentians.clauses.clause import Clause
from gentians.clauses.clause_space import ClauseSpace
from gentians.language.asp import clause_predicates, parse_program
from gentians.language.ir.example import Example
from gentians.language.ir.inductive_task import InductiveTask


def inductive_task(background: list[str], *args: Any, **kwargs: Any) -> InductiveTask:
    return InductiveTask(parse_program("\n".join(background)), *args, **kwargs)


def example(
    values: tuple[str, str] | tuple[str, str, str], positive: bool
) -> Example:
    return Example.parse(values, positive)


def make_clause_space(sources: list[str]) -> ClauseSpace:
    statements = parse_program("\n".join(sources))
    assert len(statements) == len(sources)
    assert all(statement.ast_type == ast.ASTType.Rule for statement in statements)
    entries = []
    for source, statement in zip(sources, statements, strict=True):
        heads, dependencies, body_literals = clause_predicates(statement)
        entries.append(
            Clause(source, statement, heads, dependencies, body_literals)
        )
    return ClauseSpace(entries)
