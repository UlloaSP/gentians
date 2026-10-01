from collections.abc import Callable, Iterator
from dataclasses import fields
from itertools import combinations

from ...language.asp import AspProgram, Predicate
from .ground_relations import (
    ClosedWorld,
    GroundTuple,
    _arg_distinct_violation,
    _cardinality_violation,
    _closed_world,
    _dependency_violation,
    _hold_in_every_model,
    _project_implies_violation,
    _symmetric_violation,
)
from .properties import ClosedWorldProperties, DomainKey
from .relation_properties import (
    _collect_argument_properties,
    _collect_dependency_properties,
    _collect_disjoint_projections,
    _collect_projection_implications,
    _collect_tuple_mutex,
    _domain_covers,
    _is_acyclic,
    _is_reflexive,
    _is_total_order,
    _is_transitive,
    _partition_properties,
    _position_values,
    _product_positions,
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

# Relations larger than this are left without extension-based properties: the
# pairwise checks below are quadratic, and an absent property only costs pruning.
MAX_ANALYSED_TUPLES = 10000


def _closed_world_properties(
    contexts: tuple[AspProgram, ...],
    learned: frozenset[Predicate] = frozenset(),
    relevant: frozenset[Predicate] | None = None,
    negated: frozenset[Predicate] | None = None,
) -> ClosedWorldProperties:
    """Properties that hold in every evaluation context.

    Each example is evaluated against the background plus its own context, so a
    property may prune a clause only if it holds in each of those programs
    separately. Merging contexts would invent relations that no example sees.
    """
    common: ClosedWorldProperties | None = None
    for program in contexts:
        world = _closed_world(program, learned)
        if world is None:
            continue
        properties = _context_properties(world, relevant, negated)
        del world
        common = properties if common is None else ClosedWorldProperties(*(
            getattr(common, field.name) & getattr(properties, field.name)
            for field in fields(ClosedWorldProperties)
        ))
    # Subsumption is valid only after intersection: a key present in one context
    # must not hide a functional dependency that holds in every context.
    return ClosedWorldProperties.none() if common is None else _reduced(common)


def _context_properties(
    world: ClosedWorld,
    relevant: frozenset[Predicate] | None,
    negated: frozenset[Predicate] | None,
) -> ClosedWorldProperties:
    candidates = relevant if relevant is not None else frozenset(world.extensions)
    extensions: dict[Predicate, frozenset[GroundTuple]] = {
        predicate: tuples
        for predicate in sorted(candidates)
        if (tuples := world.extension(predicate)) is not None
        and len(tuples) <= MAX_ANALYSED_TUPLES
    }
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
    universal: set[Predicate] = set()
    arg_equal: set[tuple[Predicate, int, int]] = set()
    arg_distinct: set[tuple[Predicate, int, int]] = set()
    functional: set[tuple[Predicate, int, int]] = set()
    functional_set: set[tuple[Predicate, tuple[int, ...], int]] = set()
    keys: set[tuple[Predicate, tuple[int, ...]]] = set()
    transitive: set[Predicate] = set()
    domains: dict[DomainKey, tuple[frozenset, ...]] = {}

    for predicate, tuples in extensions.items():
        _collect_argument_properties(predicate, tuples, arg_equal, arg_distinct)
        _collect_dependency_properties(predicate, tuples, functional, functional_set, keys)
        if (positions := _product_positions(predicate, tuples)) is not None:
            universal.add(predicate)
            domains[("universal", predicate)] = positions
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
            reflexive_pred = _is_reflexive(tuples)
            if reflexive_pred:
                reflexive.add(predicate)
            if tuples and tuples.isdisjoint(reversed_tuples) and transitive_pred:
                strict_order.add(predicate)
            if _is_total_order(tuples, transitive_pred, reflexive_pred):
                total_order.add(predicate)
            if predicate in reflexive or predicate in total_order:
                field = frozenset(value for row in tuples for value in row)
                domains[("field", predicate)] = (field,)

    positions_by_predicate = {predicate: _position_values(predicate[1], tuples) for predicate, tuples in extensions.items()}
    for left, right in combinations(sorted(extensions), 2):
        left_tuples = extensions[left]
        right_tuples = extensions[right]
        if left[1] == right[1]:
            if left_tuples == right_tuples:
                equivalent.add((left, right))
            elif left_tuples <= right_tuples:
                implies.add((left, right))
            elif right_tuples <= left_tuples:
                implies.add((right, left))
            if left_tuples.isdisjoint(right_tuples):
                mutex.add((left, right))
            # Complements and partitions only prune literals that are all negated.
            if left_tuples.isdisjoint(right_tuples) and (
                negated is None or {left, right} <= negated
            ):
                union = left_tuples | right_tuples
                if (positions := _product_positions(left, union)) is not None:
                    complement.add((left, right))
                    domains[("complement", left, right)] = positions
            if left[1] == 2 and left_tuples == {(b, a) for a, b in right_tuples}:
                inverse.add((left, right))
        _collect_disjoint_projections(
            left, positions_by_predicate[left], right, positions_by_predicate[right], disjoint_projection
        )
    # A closed relation inside the lower bound of a learned one implies it in
    # every model: learned clauses only add tuples to that bound.
    lower_targets = {
        predicate: world.lower_bounds.get(predicate, frozenset())
        for predicate in sorted(candidates)
        if predicate in world.open
    }
    for target, bound in lower_targets.items():
        for source, tuples in extensions.items():
            if source[1] == target[1] and tuples <= bound:
                implies.add((source, target))
    _collect_projection_implications(extensions, {**extensions, **lower_targets}, project_implies)
    _collect_tuple_mutex(extensions, tuple_mutex)
    partitions = _partition_properties(
        extensions
        if negated is None
        else {
            predicate: tuples
            for predicate, tuples in extensions.items()
            if predicate in negated
        }
    )
    for group in partitions:
        union = frozenset().union(*(extensions[predicate] for predicate in group))
        domains[("partition", group)] = _position_values(group[0][1], union)
    cardinality_upper = _syntactic_properties(
        world, keys, functional, functional_set, project_implies, arg_distinct, symmetric
    )
    # Values of an unfixed relation lie inside its brave upper bound.
    bounded = {
        **{
            predicate: tuples
            for predicate, tuples in world.upper_bounds.items()
            if predicate in candidates and len(tuples) <= MAX_ANALYSED_TUPLES
        },
        **extensions,
    }
    closed = {
        predicate
        for predicate in world.extensions.keys() | world.unfixed
        if predicate not in world.open
    } | set(extensions)
    if relevant is not None:
        closed &= relevant
    implied = closed | set(lower_targets)
    return ClosedWorldProperties(
        symmetric=frozenset(symmetric & closed),
        asymmetric=frozenset(asymmetric),
        antisymmetric=frozenset(antisymmetric),
        acyclic=frozenset(acyclic),
        reflexive=frozenset(reflexive),
        strict_order=frozenset(strict_order),
        total_order=frozenset(total_order),
        inverse=frozenset(inverse),
        implies=frozenset(implies),
        equivalent=frozenset(equivalent),
        project_implies=frozenset(
            item for item in project_implies
            if item[0] in closed and item[1] in implied
        ),
        disjoint_projection=frozenset(disjoint_projection),
        tuple_mutex=frozenset(tuple_mutex),
        mutex=frozenset(mutex),
        complement=frozenset(complement),
        partitions=frozenset(partitions),
        universal=frozenset(universal),
        empty=frozenset(
            predicate for predicate, tuples in extensions.items() if not tuples
        ),
        arg_equal=frozenset(arg_equal),
        arg_distinct=frozenset(item for item in arg_distinct if item[0] in closed),
        functional=frozenset(item for item in functional if item[0] in closed),
        functional_set=frozenset(
            item for item in functional_set if item[0] in closed
        ),
        keys=frozenset(item for item in keys if item[0] in closed),
        cardinality_upper=frozenset(
            item for item in cardinality_upper if item[0] in closed
        ),
        transitive=frozenset(transitive),
        domain_covers=frozenset(_domain_covers(domains, bounded)),
        positive_args=frozenset(_numeric_args(bounded, 1)),
        nonnegative_args=frozenset(_numeric_args(bounded, 0)),
    )


def _numeric_args(
    relations: dict[Predicate, frozenset[GroundTuple]], minimum: int
) -> Iterator[tuple[Predicate, int]]:
    for predicate, tuples in relations.items():
        for index in range(predicate[1]):
            if all(
                isinstance(value := values[index], int) and value >= minimum
                for values in tuples
            ):
                yield predicate, index


def _syntactic_properties(
    world: ClosedWorld,
    keys: set[tuple[Predicate, tuple[int, ...]]],
    functional: set[tuple[Predicate, int, int]],
    functional_set: set[tuple[Predicate, tuple[int, ...], int]],
    project_implies: set[tuple[Predicate, Predicate, tuple[int, ...]]],
    arg_distinct: set[tuple[Predicate, int, int]],
    symmetric: set[Predicate],
) -> set[tuple[Predicate, int]]:
    """Add rule-shaped properties that Clingo proves in every stable model.

    Choice rules and rule shapes suggest properties of relations whose extension
    differs between models. Syntax alone misses other definers, so each
    suggestion is kept only when no stable model violates it.
    """
    (
        choice_functional,
        choice_functional_set,
        choice_keys,
        choice_project_implies,
        choice_cardinality,
    ) = _choice_clause_properties(world.program)
    rule_keys = keys | choice_keys
    rule_functional = functional | choice_functional
    rule_functional_set = functional_set | choice_functional_set
    rule_arg_distinct = set(arg_distinct)
    rule_symmetric = set(symmetric)
    _collect_clause_defined_properties(
        rule_keys,
        rule_functional,
        rule_functional_set,
        rule_arg_distinct,
        rule_symmetric,
        world.program,
    )
    violations: dict[str, list[Callable[[], None]]] = {}

    def candidate(violation: str, add: Callable[[], None]) -> None:
        violations.setdefault(violation, []).append(add)

    for predicate, args in sorted(rule_keys - keys):
        outputs = tuple(index for index in range(predicate[1]) if index not in args)
        candidate(
            _dependency_violation(predicate, args, outputs),
            lambda item=(predicate, args): keys.add(item),
        )
    for predicate, source, target in sorted(rule_functional - functional):
        candidate(
            _dependency_violation(predicate, (source,), (target,)),
            lambda item=(predicate, source, target): functional.add(item),
        )
    for predicate, sources, target in sorted(rule_functional_set - functional_set):
        candidate(
            _dependency_violation(predicate, sources, (target,)),
            lambda item=(predicate, sources, target): functional_set.add(item),
        )
    for source, target, projection in sorted(choice_project_implies - project_implies):
        candidate(
            _project_implies_violation(source, target, projection),
            lambda item=(source, target, projection): project_implies.add(item),
        )
    for predicate, left, right in sorted(rule_arg_distinct - arg_distinct):
        candidate(
            _arg_distinct_violation(predicate, left, right),
            lambda item=(predicate, left, right): arg_distinct.add(item),
        )
    for predicate in sorted(rule_symmetric - symmetric):
        candidate(
            _symmetric_violation(predicate),
            lambda item=predicate: symmetric.add(item),
        )
    cardinality_upper: set[tuple[Predicate, int]] = set()
    for predicate, upper in sorted(choice_cardinality):
        candidate(
            _cardinality_violation(predicate, upper),
            lambda item=(predicate, upper): cardinality_upper.add(item),
        )
    accept = list(violations.values())
    for index in _hold_in_every_model(world.program, list(violations)):
        for add in accept[index]:
            add()
    return cardinality_upper


def _reduced(properties: ClosedWorldProperties) -> ClosedWorldProperties:
    """Drop facts implied by stronger facts that hold in the same contexts."""
    asymmetric = set(properties.asymmetric)
    acyclic = set(properties.acyclic)
    antisymmetric = set(properties.antisymmetric)
    reflexive = set(properties.reflexive)
    transitive = set(properties.transitive)
    strict_order = properties.strict_order
    total_order = properties.total_order
    asymmetric -= acyclic | strict_order | total_order
    acyclic -= strict_order
    antisymmetric -= asymmetric | acyclic | strict_order | total_order
    reflexive -= total_order
    transitive -= strict_order | total_order
    mutex = set(properties.mutex) - properties.complement
    arg_distinct = _without_irreflexive_subsumed_arg_distinct(
        set(properties.arg_distinct),
        set(properties.asymmetric | properties.acyclic | strict_order),
    )
    mutex = _without_partition_subsumed_mutex(mutex, set(properties.partitions))
    keys = set(properties.keys)
    functional = _without_key_subsumed_functional(set(properties.functional), keys)
    functional_set = _without_key_subsumed_functional_set(
        set(properties.functional_set), keys
    )
    functional_set = _without_subsumed_functional_set(functional_set, functional)
    surviving_domains = (
        {("field", predicate) for predicate in reflexive | total_order}
        | {("universal", predicate) for predicate in properties.universal}
        | {("complement", *pair) for pair in properties.complement}
        | {("partition", group) for group in properties.partitions}
    )
    return ClosedWorldProperties(
        symmetric=properties.symmetric,
        asymmetric=frozenset(asymmetric),
        antisymmetric=frozenset(antisymmetric),
        acyclic=frozenset(acyclic),
        reflexive=frozenset(reflexive),
        strict_order=strict_order,
        total_order=total_order,
        inverse=properties.inverse,
        implies=properties.implies,
        equivalent=properties.equivalent,
        project_implies=properties.project_implies,
        disjoint_projection=properties.disjoint_projection,
        tuple_mutex=properties.tuple_mutex,
        mutex=frozenset(mutex),
        complement=properties.complement,
        partitions=properties.partitions,
        universal=properties.universal,
        empty=properties.empty,
        arg_equal=properties.arg_equal,
        arg_distinct=frozenset(arg_distinct),
        functional=frozenset(functional),
        functional_set=frozenset(functional_set),
        keys=properties.keys,
        cardinality_upper=properties.cardinality_upper,
        transitive=frozenset(transitive),
        domain_covers=frozenset(
            cover for cover in properties.domain_covers if cover[0] in surviving_domains
        ),
        positive_args=properties.positive_args,
        nonnegative_args=properties.nonnegative_args - properties.positive_args,
    )
