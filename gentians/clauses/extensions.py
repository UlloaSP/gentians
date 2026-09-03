from collections.abc import Iterable, Iterator
from itertools import product

import clingo
from clingo import ast

from ..language.asp import Predicate, clause_predicates, symbolic_function
from ..language.ir.inductive_task import InductiveTask

type GroundTerm = ast.AST | clingo.Symbol
type GroundTuple = tuple[GroundTerm, ...]
Atom = tuple[str, tuple[ast.AST, ...], ast.Sign]
AtomPattern = tuple[str, tuple[tuple[GroundTerm | str, bool], ...]]


def _numeric_domain_values(task: InductiveTask) -> set[int]:
    nodes = _task_nodes(task)
    constants = _numeric_constants(nodes)
    return {
        value for node in nodes for value in _numeric_values(node, constants)
    }


def _numeric_constants(nodes: Iterable[ast.AST]) -> dict[str, int]:
    constants: dict[str, int] = {}
    for node in nodes:
        if node.ast_type != ast.ASTType.Definition:
            continue
        value = _integer_value(node.value, constants)
        if value is not None:
            constants[str(node.name)] = value
    return constants


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


def _defined_predicates(nodes: tuple[ast.AST, ...]) -> set[Predicate]:
    defined: set[Predicate] = set()
    for node in nodes:
        heads, _deps, _body_literals = clause_predicates(node)
        defined.update(heads)
    return defined


def _type_domains(
    nodes: tuple[ast.AST, ...],
    predicate_arg_types: dict[tuple[str, int, int], str],
) -> dict[str, set[GroundTerm]]:
    domains: dict[str, set[GroundTerm]] = {}
    constants = _numeric_constants(nodes)
    for name, arguments, _sign in _iter_atoms(nodes):
        if any(_has_variable(argument) for argument in arguments):
            continue
        arity = len(arguments)
        for values in _expand_ground_arguments(arguments, constants):
            for index, value in enumerate(values):
                arg_type = predicate_arg_types.get(
                    (name.removeprefix("-"), arity, index), "any"
                )
                if arg_type != "any":
                    domains.setdefault(arg_type, set()).add(value)
    return domains


def _universal_predicates(
    extensions: dict[Predicate, set[GroundTuple]],
    predicate_arg_types: dict[tuple[str, int, int], str],
    type_domains: dict[str, set[GroundTerm]],
    unary_type_domains: dict[str, dict[Predicate, set[GroundTerm]]],
) -> set[Predicate]:
    universal: set[Predicate] = set()
    for predicate, tuples in extensions.items():
        domains: list[set[GroundTerm]] = []
        for index in range(predicate[1]):
            arg_type = predicate_arg_types.get(
                (predicate[0].removeprefix("-"), predicate[1], index), "any"
            )
            domain = type_domains.get(arg_type, set())
            explicit_domain = set().union(
                *(
                    values
                    for source, values in unary_type_domains.get(arg_type, {}).items()
                    if source != predicate
                ),
                set(),
            )
            if arg_type == "any" or not domain or explicit_domain != domain:
                break
            domains.append(domain)
        else:
            size = 1
            for domain in domains:
                size *= len(domain)
            if size <= 10000 and tuples == set(product(*domains)):
                universal.add(predicate)
    return universal


def _unary_type_domains(
    nodes: tuple[ast.AST, ...],
    predicate_arg_types: dict[tuple[str, int, int], str],
) -> dict[str, dict[Predicate, set[GroundTerm]]]:
    domains: dict[str, dict[Predicate, set[GroundTerm]]] = {}
    constants = _numeric_constants(nodes)
    for name, arguments, _sign in _iter_atoms(nodes):
        if len(arguments) != 1 or _has_variable(arguments[0]):
            continue
        arg_type = predicate_arg_types.get((name.removeprefix("-"), 1, 0), "any")
        values = _expand_ground_argument(arguments[0], constants)
        if arg_type != "any" and values is not None:
            domains.setdefault(arg_type, {}).setdefault((name, 1), set()).update(values)
    return domains


def _task_nodes(task: InductiveTask) -> tuple[ast.AST, ...]:
    return task.background + tuple(
        node
        for example in (*task.positive_examples, *task.negative_examples)
        for node in (*example.included, *example.excluded, *example.context)
    )


def _iter_atoms(nodes: Iterable[ast.AST]) -> Iterator[Atom]:
    for node in nodes:
        yield from _node_atoms(node)


def _node_atoms(
    node: ast.AST, sign: ast.Sign = ast.Sign.NoSign
) -> tuple[Atom, ...]:
    if node.ast_type == ast.ASTType.Literal:
        return _node_atoms(
            node.atom, node.sign if node.sign != ast.Sign.NoSign else sign
        )
    if node.ast_type == ast.ASTType.SymbolicAtom:
        parsed = symbolic_function(node.symbol)
        if parsed is not None:
            name, arguments = parsed
            return ((name, tuple(arguments), sign),)
        return ()
    return tuple(
        atom
        for child in _children(node)
        for atom in _node_atoms(child, sign)
    )


def _numeric_values(node: ast.AST, constants: dict[str, int]) -> Iterator[int]:
    value = _integer_value(node, constants)
    if value is not None:
        yield value
        return
    if node.ast_type == ast.ASTType.Interval:
        start = _integer_value(node.left, constants)
        end = _integer_value(node.right, constants)
        if start is not None and end is not None and 0 <= end - start <= 10000:
            yield from range(start, end + 1)
        return
    for child in _children(node):
        yield from _numeric_values(child, constants)


def _integer_value(term: ast.AST, constants: dict[str, int]) -> int | None:
    if term.ast_type == ast.ASTType.SymbolicTerm:
        symbol = term.symbol
        if symbol.type == clingo.SymbolType.Number:
            return int(symbol.number)
        if symbol.type == clingo.SymbolType.Function and not symbol.arguments:
            return constants.get(symbol.name)
    if (
        term.ast_type == ast.ASTType.UnaryOperation
        and term.operator_type == ast.UnaryOperator.Minus
    ):
        value = _integer_value(term.argument, constants)
        return -value if value is not None else None
    return None


def _has_variable(node: ast.AST) -> bool:
    return _contains(node, ast.ASTType.Variable)


def _contains(node: ast.AST, ast_type: ast.ASTType) -> bool:
    return node.ast_type == ast_type or any(
        _contains(child, ast_type) for child in _children(node)
    )


def _children(node: ast.AST) -> Iterator[ast.AST]:
    for key in node.child_keys:
        child = getattr(node, key)
        if isinstance(child, ast.AST):
            yield child
        elif isinstance(child, ast.ASTSequence):
            yield from (item for item in child if isinstance(item, ast.AST))


def _ground_key(term: ast.AST, constants: dict[str, int]) -> GroundTerm:
    number = _integer_value(term, constants)
    return clingo.Number(number) if number is not None else term
