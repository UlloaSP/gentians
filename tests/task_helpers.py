import random
from typing import Any

from clingo import ast

from gentians.clauses.clause import Clause
from gentians.clauses.clause_space import ClauseSpace
from gentians.clauses.metadata import ClauseMetadata
from gentians.language.asp import clause_predicates, parse_program
from gentians.language.ir.example import Example
from gentians.language.ir.inductive_task import InductiveTask


def feature_task_text(features: int) -> str:
    """Deterministic constraint task whose clauses are subsets of unary features."""
    rng = random.Random(20260908)
    pairs = min(6, features // 2)

    def valid(mask: int) -> bool:
        return not any(mask & (3 << (2 * pair)) == 3 << (2 * pair)
                       for pair in range(pairs))

    # Singleton positives prevent rejecting a feature without its partner.
    # The all-true negative ensures all feature conjunctions can co-occur.
    positives = {0, *(1 << feature for feature in range(features))}
    negatives = {(1 << features) - 1}
    for _ in range(256):
        mask = rng.getrandbits(features)
        target = positives if valid(mask) else negatives
        limit = features + 25 if valid(mask) else 25
        if len(target) < limit:
            target.add(mask)
    worlds = [(mask, True) for mask in sorted(positives)]
    worlds += [(mask, False) for mask in sorted(negatives)]
    lines = [
        "#maxv(1).", "#maxbl(6).", "#maxhl(0).", "#maxpl(6).",
        f"world(0..{len(worlds) - 1}).",
        "1 { active(X) : world(X) } 1.",
    ]
    for feature in range(features):
        lines.append(f"f{feature}(X) :- active(X), has{feature}(X).")
        lines.extend(f"has{feature}({world})." for world, (mask, _) in enumerate(worlds)
                     if mask & (1 << feature))
        lines.append(f"#modeb(1,f{feature}(var(world,output))).")
    lines.extend(f"#{'pos' if positive else 'neg'}({{active({world})}}, {{}})."
                 for world, (_, positive) in enumerate(worlds))
    return "\n".join(lines) + "\n"


def inductive_task(background: list[str], *args: Any, **kwargs: Any) -> InductiveTask:
    return InductiveTask(parse_program("\n".join(background)), *args, **kwargs)


def example(values: tuple[str, str] | tuple[str, str, str], positive: bool) -> Example:
    return Example.parse(tuple((value.strip(), 1, 1) for value in values), positive)


def make_clause_space(sources: list[str]) -> ClauseSpace:
    statements = parse_program("\n".join(sources))
    assert len(statements) == len(sources)
    assert all(statement.ast_type == ast.ASTType.Rule for statement in statements)
    entries = []
    for source, statement in zip(sources, statements, strict=True):
        heads, dependencies, body_literals = clause_predicates(statement)
        entries.append(Clause(source, statement, ClauseMetadata.from_predicates(heads, dependencies, body_literals)))
    return ClauseSpace(entries)
