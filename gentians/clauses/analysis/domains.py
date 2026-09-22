from itertools import product

from clingo import ast

from ...language.asp import Predicate
from ...language.ir.inductive_task import InductiveTask
from .ast_inspection import (
    _has_variable,
    _iter_atoms,
    _numeric_constants,
    _numeric_values,
)
from .ground_relations import (
    GroundTerm,
    GroundTuple,
    _expand_ground_argument,
    _expand_ground_arguments,
)
from .task import _task_nodes


def _numeric_domain_values(task: InductiveTask) -> set[int]:
    nodes = _task_nodes(task)
    constants = _numeric_constants(nodes)
    return {
        value for node in nodes for value in _numeric_values(node, constants)
    }


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
