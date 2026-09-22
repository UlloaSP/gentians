from clingo import ast

from ..language.asp import (
    clause_predicates,
    symbolic_function,
    symbolic_literal_predicate,
)
from ..language.ir.atom_literal import AtomLiteral
from ..language.ir.inductive_task import InductiveTask
from .analysis.ast_inspection import _children
from .analysis.task import _head_atoms
from .clause_mode import ClauseMode
from .reified_clause import ReifiedClause
from .reified_literal import ReifiedLiteral


def _theta_reduced(
    clause: ReifiedClause,
    modes: dict[int, ClauseMode],
) -> bool:
    """Reject normal clauses θ-equivalent to one of their proper subclauses."""
    literals = (*clause.head, *clause.body)
    if any(
        not isinstance(modes[literal.mode_id].literal, AtomLiteral)
        for literal in literals
    ):
        return True
    signatures = tuple((literal.section, literal.mode_id) for literal in literals)
    repeated = {
        signature for signature in signatures if signatures.count(signature) > 1
    }
    if not repeated:
        return True
    return not any(
        _theta_subsumes(literals, literals[:index] + literals[index + 1 :])
        for index in range(len(literals))
        if signatures[index] in repeated
    )


def _theta_subsumes(
    source: tuple[ReifiedLiteral, ...],
    target: tuple[ReifiedLiteral, ...],
) -> bool:
    candidates = {
        literal: tuple(
            candidate
            for candidate in target
            if (candidate.section, candidate.mode_id)
            == (literal.section, literal.mode_id)
        )
        for literal in source
    }
    if any(not matches for matches in candidates.values()):
        return False
    ordered = sorted(source, key=lambda literal: len(candidates[literal]))

    def match(index: int, substitution: dict[int, int]) -> bool:
        if index == len(ordered):
            return True
        literal = ordered[index]
        for candidate in candidates[literal]:
            extended = substitution.copy()
            if all(
                extended.setdefault(variable, target_variable) == target_variable
                for variable, target_variable in zip(
                    literal.variables, candidate.variables, strict=True
                )
            ) and match(index + 1, extended):
                return True
        return False

    return match(0, {})


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
    # Predicate extraction does not expand pooled symbolic heads such as
    # q(a;b). Never mistake an unrecognized head for a missing definition.
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
    if node.ast_type == ast.ASTType.SymbolicAtom:
        return symbolic_function(node.symbol) is not None
    if node.ast_type == ast.ASTType.TheoryAtom:
        return False
    return all(_known_head(child) for child in _children(node))
