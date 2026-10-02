from clingo import ast

from ..language.asp import (
    clause_predicates,
    symbolic_functions,
    symbolic_literal_predicate,
)
from ..language.ir.inductive_task import InductiveTask
from .analysis.ast_inspection import _children
from .analysis.task import _head_atoms


def _prune_optional_constraints(task: InductiveTask) -> bool:
    """Prove that a perfect nonempty hypothesis must contain a learned head.

    Pure constraints only remove stable models, so without negative examples
    they are optional in a hypothesis that already contains headed clauses.
    Absence of negatives alone is insufficient: a constraint-only program can
    be the only legal solution when the background already covers the positives.
    Use a missing positive predicate as a cheap sufficient proof, not a coverage
    approximation. Unknown directives keep their full space.
    """
    if (task.negative_examples or not task.positive_examples
            or task.max_head_literals == 0):
        return False
    # Never mistake an unrecognized head for a missing definition.
    if any(
        node.ast_type != ast.ASTType.Rule or not _known_head(node.head)
        for node in task.background
    ):
        return False
    if not _head_atoms(task):
        return False
    background_heads = set().union(*(clause_predicates(node)[0] for node in task.background))
    for example in task.positive_examples:
        # Inspect each isolated context separately. In particular, do not treat
        # externals or #const substitutions as ordinary rule definitions.
        if any(
            node.ast_type != ast.ASTType.Rule or not _known_head(node.head)
            for node in example.context
        ):
            continue
        providers = background_heads.union(
            *(clause_predicates(node)[0] for node in example.context)
        )
        if any(symbolic_literal_predicate(atom) not in providers for atom in example.included):
            return True
    return False


def _known_head(node: ast.AST) -> bool:
    """Whether predicate extraction understands every symbolic head element."""
    pending = [node]
    while pending:
        node = pending.pop()
        if node.ast_type == ast.ASTType.SymbolicAtom:
            if not symbolic_functions(node.symbol):
                return False
        elif node.ast_type == ast.ASTType.TheoryAtom:
            return False
        else:
            pending.extend(reversed(tuple(_children(node))))
    return True
