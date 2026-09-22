from itertools import combinations

from clingo import ast

from ...language.asp import AspProgram, Predicate
from .ast_inspection import _defined_predicates
from .domains import _type_domains, _unary_type_domains, _universal_predicates
from .ground_relations import GroundTuple, _closed_world_extensions
from .properties import ClosedWorldProperties
from .relation_properties import (
    _collect_argument_properties,
    _collect_composite_functional_properties,
    _collect_disjoint_projections,
    _collect_functional_properties,
    _collect_key_properties,
    _collect_projection_implications,
    _collect_tuple_mutex,
    _is_acyclic,
    _is_reflexive,
    _is_total_order,
    _is_transitive,
    _partition_properties,
    _without_irreflexive_subsumed_arg_distinct,
    _without_key_subsumed_functional,
    _without_key_subsumed_functional_set,
    _without_partition_subsumed_mutex,
    _without_subsumed_functional_set,
)
from .rule_properties import (
    _choice_clause_properties,
    _collect_clause_defined_properties,
)


def _closed_world_properties(
    nodes: tuple[ast.AST, ...],
    predicate_arg_types: dict[tuple[str, int, int], str] | None = None,
    closed_body_predicates: set[Predicate] | None = None,
    statements: AspProgram | None = None,
) -> ClosedWorldProperties:
    extensions = _closed_world_extensions(nodes)
    property_program = statements or tuple(
        node for node in nodes if node.ast_type == ast.ASTType.Rule
    )
    symmetric: set[Predicate] = set()
    asymmetric: set[Predicate] = set()
    antisymmetric: set[Predicate] = set()
    acyclic: set[Predicate] = set()
    reflexive: set[Predicate] = set()
    strict_order: set[Predicate] = set()
    total_order: set[Predicate] = set()
    inverse: set[tuple[Predicate, Predicate]] = set()
    implies: set[tuple[Predicate, Predicate]] = set()
    equivalent: set[tuple[Predicate, Predicate]] = set()
    project_implies: set[tuple[Predicate, Predicate, tuple[int, ...]]] = set()
    disjoint_projection: set[tuple[Predicate, int, Predicate, int]] = set()
    tuple_mutex: set[tuple[Predicate, Predicate, tuple[int, ...]]] = set()
    mutex: set[tuple[Predicate, Predicate]] = set()
    complement: set[tuple[Predicate, Predicate]] = set()
    partitions: set[tuple[Predicate, ...]] = set()
    universal: set[Predicate] = set()
    empty: set[Predicate] = set()
    arg_equal: set[tuple[Predicate, int, int]] = set()
    arg_distinct: set[tuple[Predicate, int, int]] = set()
    functional: set[tuple[Predicate, int, int]] = set()
    functional_set: set[tuple[Predicate, tuple[int, ...], int]] = set()
    keys: set[tuple[Predicate, tuple[int, ...]]] = set()
    cardinality_upper: set[tuple[Predicate, int]] = set()
    transitive: set[Predicate] = set()
    tuple_universe_by_arity: dict[int, set[GroundTuple]] = {}
    (
        choice_functional,
        choice_functional_set,
        choice_keys,
        choice_project_implies,
        choice_cardinality_upper,
    ) = _choice_clause_properties(property_program)
    for predicate, tuples in extensions.items():
        tuple_universe_by_arity.setdefault(predicate[1], set()).update(tuples)

    for predicate, tuples in extensions.items():
        _collect_argument_properties(predicate, tuples, arg_equal, arg_distinct)
        _collect_functional_properties(predicate, tuples, functional)
        _collect_composite_functional_properties(predicate, tuples, functional_set)
        _collect_key_properties(predicate, tuples, keys)
        if predicate[1] == 2:
            reversed_tuples = {(right, left) for left, right in tuples}
            if tuples == reversed_tuples:
                symmetric.add(predicate)
            if tuples.isdisjoint(reversed_tuples):
                asymmetric.add(predicate)
            if all(
                left == right or (right, left) not in tuples for left, right in tuples
            ):
                antisymmetric.add(predicate)
            if _is_acyclic(tuples):
                acyclic.add(predicate)
            transitive_pred = _is_transitive(tuples)
            if transitive_pred:
                transitive.add(predicate)
            if _is_reflexive(tuples):
                reflexive.add(predicate)
            if tuples and tuples.isdisjoint(reversed_tuples) and transitive_pred:
                strict_order.add(predicate)
            if _is_total_order(tuples):
                total_order.add(predicate)

    for left, right in combinations(sorted(extensions), 2):
        left_tuples = extensions[left]
        right_tuples = extensions[right]
        if left[1] == right[1]:
            if left_tuples == right_tuples:
                equivalent.add((min(left, right), max(left, right)))
            elif left_tuples <= right_tuples:
                implies.add((left, right))
            elif right_tuples <= left_tuples:
                implies.add((right, left))
            if left_tuples.isdisjoint(right_tuples):
                universe = tuple_universe_by_arity[left[1]]
                if left_tuples | right_tuples == universe:
                    complement.add((min(left, right), max(left, right)))
                else:
                    mutex.add((min(left, right), max(left, right)))
            if left[1] == 2 and left_tuples == {(b, a) for a, b in right_tuples}:
                inverse.add((min(left, right), max(left, right)))
        _collect_disjoint_projections(
            left, left_tuples, right, right_tuples, disjoint_projection
        )
        _collect_projection_implications(
            left, left_tuples, right, right_tuples, project_implies
        )
        _collect_projection_implications(
            right, right_tuples, left, left_tuples, project_implies
        )
    if closed_body_predicates:
        _collect_tuple_mutex(extensions, closed_body_predicates, tuple_mutex)
    functional.update(choice_functional)
    functional_set.update(choice_functional_set)
    keys.update(choice_keys)
    project_implies.update(choice_project_implies)
    cardinality_upper.update(choice_cardinality_upper)
    _collect_clause_defined_properties(
        keys,
        functional,
        functional_set,
        arg_distinct,
        symmetric,
        property_program,
    )
    partitions.update(_partition_properties(extensions, tuple_universe_by_arity))
    if predicate_arg_types:
        type_domains = _type_domains(nodes, predicate_arg_types)
        unary_type_domains = _unary_type_domains(nodes, predicate_arg_types)
        universal.update(
            _universal_predicates(
                extensions,
                predicate_arg_types,
                type_domains,
                unary_type_domains,
            )
        )
    if closed_body_predicates:
        empty.update(
            predicate
            for predicate in closed_body_predicates
            if predicate not in extensions
            and predicate not in _defined_predicates(nodes)
        )
    asymmetric -= acyclic | strict_order | total_order
    acyclic -= strict_order
    antisymmetric -= acyclic | strict_order | total_order
    reflexive -= total_order | universal
    transitive -= strict_order | total_order
    mutex -= complement
    arg_distinct = _without_irreflexive_subsumed_arg_distinct(
        arg_distinct,
        asymmetric | acyclic | strict_order,
    )
    mutex = _without_partition_subsumed_mutex(mutex, partitions)
    functional = _without_key_subsumed_functional(functional, keys)
    functional_set = _without_key_subsumed_functional_set(functional_set, keys)
    functional_set = _without_subsumed_functional_set(functional_set, functional)

    return ClosedWorldProperties(
        frozenset(symmetric),
        frozenset(asymmetric),
        frozenset(antisymmetric),
        frozenset(acyclic),
        frozenset(reflexive),
        frozenset(strict_order),
        frozenset(total_order),
        frozenset(inverse),
        frozenset(implies),
        frozenset(equivalent),
        frozenset(project_implies),
        frozenset(disjoint_projection),
        frozenset(tuple_mutex),
        frozenset(mutex),
        frozenset(complement),
        frozenset(partitions),
        frozenset(universal),
        frozenset(empty),
        frozenset(arg_equal),
        frozenset(arg_distinct),
        frozenset(functional),
        frozenset(functional_set),
        frozenset(keys),
        frozenset(cardinality_upper),
        frozenset(transitive),
    )
