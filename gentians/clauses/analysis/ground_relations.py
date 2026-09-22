from itertools import product

import clingo
from clingo import ast

from ...language.asp import Predicate, symbolic_function
from .ast_inspection import (
    Atom,
    _contains,
    _has_variable,
    _integer_value,
    _iter_atoms,
    _numeric_constants,
)

type GroundTerm = ast.AST | clingo.Symbol


type GroundTuple = tuple[GroundTerm, ...]


AtomPattern = tuple[str, tuple[tuple[GroundTerm | str, bool], ...]]


def _closed_world_extensions(
    nodes: tuple[ast.AST, ...],
) -> dict[Predicate, set[GroundTuple]]:
    extensions: dict[Predicate, set[GroundTuple]] = {}
    constants = _numeric_constants(nodes)
    for name, arguments, _sign in _iter_atoms(nodes):
        if any(_has_variable(argument) for argument in arguments):
            continue
        key = (name, len(arguments))
        for values in _expand_ground_arguments(arguments, constants):
            extensions.setdefault(key, set()).add(values)
    _derive_closed_world_extensions(nodes, extensions, constants)
    return extensions


def _derive_closed_world_extensions(
    nodes: tuple[ast.AST, ...],
    extensions: dict[Predicate, set[GroundTuple]],
    constants: dict[str, int],
    limit: int = 10000,
) -> None:
    clauses = tuple(
        clause
        for clause in nodes
        if clause.ast_type == ast.ASTType.Rule and clause.body
    )
    changed = True
    while changed:
        changed = False
        for clause in clauses:
            derived = _derive_closed_world_clause(
                clause, extensions, constants, limit
            )
            for predicate, tuples in derived.items():
                current = extensions.setdefault(predicate, set())
                if len(current) + len(tuples - current) > limit:
                    continue
                before = len(current)
                current.update(tuples)
                changed |= len(current) != before


def _derive_closed_world_clause(
    clause: ast.AST,
    extensions: dict[Predicate, set[GroundTuple]],
    constants: dict[str, int],
    limit: int,
) -> dict[Predicate, set[GroundTuple]]:
    head = _literal_atom(clause.head)
    if head is None:
        return {}
    head_name, head_terms, head_negated = head
    if head_negated != ast.Sign.NoSign or any(
        term.ast_type != ast.ASTType.Variable for term in head_terms
    ):
        return {}

    positive: list[AtomPattern] = []
    negative: list[AtomPattern] = []
    for literal in clause.body:
        atom = _literal_atom(literal)
        if atom is None:
            return {}
        name, terms, sign = atom
        if sign == ast.Sign.DoubleNegation:
            return {}
        pattern = (
            name,
            tuple(_term_pattern(term, constants) for term in terms),
        )
        (negative if sign == ast.Sign.Negation else positive).append(pattern)
    if not positive or len(negative) > 1:
        return {}
    if negative and (negative[0][0], len(negative[0][1])) not in extensions:
        return {}

    assignments: list[dict[str, GroundTerm]] = [{}]
    for name, arguments in positive:
        tuples = extensions.get((name, len(arguments)))
        if tuples is None:
            return {}
        next_assignments: list[dict[str, GroundTerm]] = []
        for assignment in assignments:
            for values in tuples:
                merged = _merge_assignment(assignment, arguments, values)
                if merged is not None:
                    next_assignments.append(merged)
                    if len(next_assignments) > limit:
                        return {}
        assignments = next_assignments

    tuples: set[GroundTuple] = set()
    head_variables = tuple(str(term.name) for term in head_terms)
    for assignment in assignments:
        if negative and _negative_atom_holds(negative[0], assignment, extensions):
            continue
        try:
            tuples.add(tuple(assignment[variable] for variable in head_variables))
        except KeyError:
            return {}
    return {(head_name, len(head_terms)): tuples}


def _literal_atom(literal: ast.AST) -> Atom | None:
    if (
        literal.ast_type != ast.ASTType.Literal
        or literal.atom.ast_type != ast.ASTType.SymbolicAtom
    ):
        return None
    parsed = symbolic_function(literal.atom.symbol)
    if parsed is None:
        return None
    name, arguments = parsed
    return name, tuple(arguments), literal.sign


def _term_pattern(
    term: ast.AST, constants: dict[str, int]
) -> tuple[GroundTerm | str, bool]:
    if term.ast_type == ast.ASTType.Variable:
        return str(term.name), True
    return _ground_key(term, constants), False


def _merge_assignment(
    assignment: dict[str, GroundTerm],
    arguments: tuple[tuple[GroundTerm | str, bool], ...],
    values: GroundTuple,
) -> dict[str, GroundTerm] | None:
    merged = dict(assignment)
    for (argument, variable), value in zip(arguments, values, strict=True):
        if variable:
            variable_name = str(argument)
            if variable_name in merged and merged[variable_name] != value:
                return None
            merged[variable_name] = value
        elif argument != value:
            return None
    return merged


def _negative_atom_holds(
    atom: AtomPattern,
    assignment: dict[str, GroundTerm],
    extensions: dict[Predicate, set[GroundTuple]],
) -> bool:
    name, arguments = atom
    values: list[GroundTerm] = []
    for argument, variable in arguments:
        if variable:
            variable_name = str(argument)
            if variable_name not in assignment:
                return False
            values.append(assignment[variable_name])
        else:
            assert not isinstance(argument, str)
            values.append(argument)
    return tuple(values) in extensions.get((name, len(arguments)), set())


def _expand_ground_arguments(
    arguments: tuple[ast.AST, ...],
    constants: dict[str, int],
    limit: int = 10000,
) -> list[GroundTuple]:
    domains: list[list[GroundTerm]] = []
    size = 1
    for argument in arguments:
        values = _expand_ground_argument(argument, constants)
        if values is None:
            return []
        size *= len(values)
        if size > limit:
            return []
        domains.append(values)
    return [tuple(values) for values in product(*domains)]


def _expand_ground_argument(
    argument: ast.AST, constants: dict[str, int]
) -> list[GroundTerm] | None:
    if argument.ast_type == ast.ASTType.Interval:
        start = _integer_value(argument.left, constants)
        end = _integer_value(argument.right, constants)
        if start is None or end is None or start > end or end - start > 10000:
            return None
        return [clingo.Number(value) for value in range(start, end + 1)]
    if _has_variable(argument) or _contains(argument, ast.ASTType.Interval):
        return None
    return [_ground_key(argument, constants)]


def _ground_key(term: ast.AST, constants: dict[str, int]) -> GroundTerm:
    number = _integer_value(term, constants)
    return clingo.Number(number) if number is not None else term
