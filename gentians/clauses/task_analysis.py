import clingo
from clingo import ast

from .extensions import AstKey, _ast_key, _has_variable, _iter_atoms, _task_nodes
from ..language.ir.aggregate_declaration import AggregateDeclaration
from ..language.ir.atom_literal import AtomLiteral
from ..language.ir.atom_template import AtomTemplate
from ..language.ir.conditional_literal import ConditionalLiteral
from .clause_capabilities import ClauseCapabilities
from ..language.ir.mode_declaration import ModeDeclaration
from ..language.ir.operator_declaration import OperatorDeclaration
from ..language.asp import (
    AspProgram,
    Predicate,
)
from ..language.ir.inductive_task import InductiveTask

def _recursive_predicates(task: InductiveTask) -> set[Predicate]:
    head_predicates = {atom.signature for atom in _head_atoms(task)}
    return {
        literal.atom.signature
        for md in (*task.language_bias_body, *task.language_bias_condition)
        for literal in _mode_atom_literals(md)
        if not literal.default_negated and literal.atom.signature in head_predicates
    }


def _head_atoms(task: InductiveTask) -> tuple[AtomTemplate, ...]:
    return tuple(
        atom
        for declaration in task.language_bias_head
        for atom in declaration.template.elements
    ) + tuple(
        mode.literal.atom
        for mode in (
            *task.language_bias_aggregate_head,
            *task.language_bias_disjunctive_head,
        )
        if isinstance(mode.literal, AtomLiteral)
    )


def _mode_atom_literals(mode: ModeDeclaration) -> tuple[AtomLiteral, ...]:
    if isinstance(mode.literal, AtomLiteral):
        return (mode.literal,)
    if isinstance(mode.literal, ConditionalLiteral):
        return tuple(
            literal
            for literal in (mode.literal.conclusion, *mode.literal.conditions)
            if isinstance(literal, AtomLiteral)
        )
    return ()


def _validate_invented_predicates(
    task: InductiveTask, nodes: tuple[ast.AST, ...]
) -> None:
    invented = set(task.invented_predicates)
    if len(invented) != len(task.invented_predicates):
        raise ValueError("duplicate invented predicate")
    heads = {atom.signature for atom in _head_atoms(task)}
    positive_bodies = {
        literal.atom.signature
        for mode in task.language_bias_body
        for literal in _mode_atom_literals(mode)[:1]
        if not literal.default_negated
    }
    missing = invented - (heads & positive_bodies)
    if missing:
        raise ValueError(
            f"invented predicates require generated head and positive body modes: {sorted(missing)}"
        )
    observed = invented & _observed_predicates(nodes)
    if observed:
        raise ValueError(
            f"invented predicates must not be observed: {sorted(observed)}"
        )


def _clause_capabilities(
    task: InductiveTask,
    predicate_arg_types: dict[tuple[str, int, int], str],
    aggregate_specs: list[AggregateDeclaration],
) -> ClauseCapabilities:
    numeric_evidence = any(
        arg_type == "numeric" for arg_type in predicate_arg_types.values()
    )
    comparison_operators = {
        mode.operator
        for mode in task.arithmetic_modes
        if isinstance(mode, OperatorDeclaration)
        and mode.operator in {"eq", "neq", "lt", "leq", "gt", "geq"}
    }
    equality_comparison = bool({"eq", "neq"} & comparison_operators)
    numeric_comparison = numeric_evidence and bool(
        comparison_operators & {"lt", "leq", "gt", "geq"}
    )
    return ClauseCapabilities(
        has_numeric_evidence=numeric_evidence,
        allow_numeric_comparison=numeric_comparison,
        allow_equality_comparison=equality_comparison,
        allow_arithmetic=numeric_evidence and bool(task.arithmetic_modes),
        allow_aggregates=bool(aggregate_specs),
        allow_recursion=bool(_recursive_predicates(task)),
    )


def _available_predicates(
    task: InductiveTask, nodes: tuple[ast.AST, ...]
) -> set[tuple[str, int]]:
    predicates = {atom.signature for atom in _head_atoms(task)} | {
        literal.atom.signature
        for mode in (*task.language_bias_body, *task.language_bias_condition)
        for literal in _mode_atom_literals(mode)
    }
    predicates.update(
        (name, len(arguments)) for name, arguments, _negative in _iter_atoms(nodes)
    )
    return predicates


def _observed_predicates(nodes: tuple[ast.AST, ...]) -> set[Predicate]:
    return {
        (name, len(arguments)) for name, arguments, _negative in _iter_atoms(nodes)
    }


def _predicate_arg_types(
    task: InductiveTask, nodes: tuple[ast.AST, ...]
) -> dict[tuple[str, int, int], str]:
    declared_atoms = [
        *_head_atoms(task),
        *(
            literal.atom
            for mode in (*task.language_bias_body, *task.language_bias_condition)
            for literal in _mode_atom_literals(mode)
        ),
    ]
    positions = {
        (*atom.unsigned_signature, arg)
        for atom in declared_atoms
        for arg in range(len(atom.terms))
    }
    constants_by_position: dict[tuple[str, int, int], set[tuple[AstKey, bool]]] = {
        position: set() for position in positions
    }
    variable_position_groups: list[list[tuple[str, int, int]]] = []
    for node in nodes:
        positions_by_variable: dict[str, list[tuple[str, int, int]]] = {}
        for name, arguments, _negative in _iter_atoms((node,)):
            name = name.removeprefix("-")
            arity = len(arguments)
            for index, argument in enumerate(arguments):
                position = (name, arity, index)
                positions.add(position)
                if argument.ast_type == ast.ASTType.Variable:
                    positions_by_variable.setdefault(
                        str(argument.name), []
                    ).append(position)
                elif _has_variable(argument):
                    continue
                else:
                    constants_by_position.setdefault(position, set()).add(
                        (_ast_key(argument), _is_numeric_term(argument))
                    )
        variable_position_groups.extend(
            group for group in positions_by_variable.values() if len(group) > 1
        )

    parent = {position: position for position in positions}

    def find(position: tuple[str, int, int]) -> tuple[str, int, int]:
        while parent[position] != position:
            parent[position] = parent[parent[position]]
            position = parent[position]
        return position

    def union(left: tuple[str, int, int], right: tuple[str, int, int]) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for shared_positions in variable_position_groups:
        for other in shared_positions[1:]:
            union(shared_positions[0], other)

    constants_by_root: dict[tuple[str, int, int], set[tuple[AstKey, bool]]] = {}
    for position in positions:
        root = find(position)
        constants_by_root.setdefault(root, set()).update(
            constants_by_position.get(position, set())
        )

    declared_types_by_root: dict[tuple[str, int, int], set[str]] = {}
    for atom in declared_atoms:
        for index, argument in enumerate(atom.terms):
            if argument.kind not in {"variable", "constant"}:
                continue
            position = (*atom.unsigned_signature, index)
            declared_types_by_root.setdefault(find(position), set()).add(argument.type)
    type_by_root: dict[tuple[str, int, int], str] = {}
    next_type = 0
    for root, constants in constants_by_root.items():
        if len(declared_types_by_root.get(root, ())) == 1:
            type_by_root[root] = next(iter(declared_types_by_root[root]))
        elif constants and all(numeric for _value, numeric in constants):
            type_by_root[root] = "numeric"
        elif constants:
            type_by_root[root] = f"type_{next_type}"
            next_type += 1
        else:
            type_by_root[root] = "any"

    return {position: type_by_root[find(position)] for position in positions}


def _is_numeric_term(term: ast.AST) -> bool:
    if term.ast_type == ast.ASTType.SymbolicTerm:
        return term.symbol.type == clingo.SymbolType.Number
    if term.ast_type == ast.ASTType.Interval:
        return _is_numeric_bound(term.left) and _is_numeric_bound(term.right)
    if term.ast_type == ast.ASTType.UnaryOperation:
        return _is_numeric_term(term.argument)
    return False


def _is_numeric_bound(term: ast.AST) -> bool:
    return _is_numeric_term(term) or (
        term.ast_type == ast.ASTType.SymbolicTerm
        and term.symbol.type == clingo.SymbolType.Function
        and not term.symbol.arguments
    )


def _closed_world_nodes(task: InductiveTask) -> tuple[ast.AST, ...]:
    return task.background + tuple(
        statement
        for example in (*task.positive_examples, *task.negative_examples)
        for statement in example.context
    )


def _closed_world_program(task: InductiveTask) -> AspProgram:
    return task.background + tuple(
        statement
        for example in task.positive_examples
        for statement in example.context
    )


def _valid_aggregate_specs(
    task: InductiveTask,
    nodes: tuple[ast.AST, ...] | None = None,
) -> list[AggregateDeclaration]:
    if not task.aggregate_modes:
        return []
    available = _available_predicates(task, nodes or _task_nodes(task))
    valid = []
    for spec in task.aggregate_modes:
        if all(atom in available for atom in spec.atoms):
            valid.append(spec)
    return valid
