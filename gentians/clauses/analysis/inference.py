from collections.abc import Callable
from dataclasses import fields
from functools import lru_cache
from itertools import combinations, product

from clingo import ast

from ...language.asp import AspProgram, Predicate
from .ground_relations import (
    ClosedWorld,
    GroundTuple,
    _arg_distinct_violation,
    _cardinality_violation,
    _closed_world,
    _consequences,
    _dependency_violation,
    _hold_in_every_model,
    _project_implies_violation,
    _symmetric_violation,
)
from .properties import ClosedWorldProperties, DomainKey
from .relation_properties import (
    _collect_argument_properties,
    _collect_dependency_properties,
    _disjoint_position_pairs,
    _collect_projection_implications,
    _collect_tuple_mutex,
    _binary_successors,
    _domain_covers,
    _is_acyclic,
    _is_reflexive,
    _is_total_order,
    _is_transitive,
    _key_sets_by_predicate,
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
    _RuleSyntax,
    _rule_syntax,
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
    relations: dict[ast.AST, tuple[frozenset[Predicate], frozenset[Predicate]]] = {}
    # Retain only a small window of native bounds, never Clingo controls or
    # worlds. Classification and proofs remain separate for each context.
    consequences = lru_cache(maxsize=8)(_consequences)
    syntax = lru_cache(maxsize=8)(_rule_syntax)
    for program in contexts:
        world = _closed_world(program, learned, relations, consequences)
        if world is None:
            continue
        properties = _context_properties(world, relevant, negated, syntax(world.program))
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
    syntax: _RuleSyntax | None = None,
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
    groups: dict[tuple[int, frozenset[GroundTuple]], list[Predicate]] = {}
    for predicate, tuples in extensions.items():
        groups.setdefault((predicate[1], tuples), []).append(predicate)
    positions_by_predicate = {}
    reversed_by_predicate = {}
    for (arity, tuples), predicates in groups.items():
        representative = predicates[0]
        equal_args, distinct_args, dependencies, composite_dependencies, extension_keys = set(), set(), set(), set(), set()
        _collect_argument_properties(representative, tuples, equal_args, distinct_args)
        _collect_dependency_properties(representative, tuples, dependencies, composite_dependencies, extension_keys)
        positions = _position_values(arity, tuples)
        product_positions = _product_positions(positions, len(tuples))
        for predicate in predicates:
            positions_by_predicate[predicate] = positions
            arg_equal.update((predicate, left, right) for _, left, right in equal_args)
            arg_distinct.update((predicate, left, right) for _, left, right in distinct_args)
            functional.update((predicate, source, target) for _, source, target in dependencies)
            functional_set.update((predicate, sources, target) for _, sources, target in composite_dependencies)
            keys.update((predicate, args) for _, args in extension_keys)
            if product_positions is not None:
                universal.add(predicate)
                domains[("universal", predicate)] = product_positions
        if arity == 2:
            reversed_tuples = frozenset((right, left) for left, right in tuples)
            for predicate in predicates:
                reversed_by_predicate[predicate] = reversed_tuples
            if tuples == reversed_tuples:
                symmetric.update(predicates)
            asymmetric_pred = tuples.isdisjoint(reversed_tuples)
            if asymmetric_pred:
                asymmetric.update(predicates)
            antisymmetric_pred = all(
                left == right or (right, left) not in tuples for left, right in tuples
            )
            if antisymmetric_pred:
                antisymmetric.update(predicates)
            successors = _binary_successors(tuples)
            if _is_acyclic(successors):
                acyclic.update(predicates)
            transitive_pred = _is_transitive(successors, len(tuples))
            if transitive_pred:
                transitive.update(predicates)
            field = positions[0] | positions[1]
            reflexive_pred = _is_reflexive(tuples, field)
            if reflexive_pred:
                reflexive.update(predicates)
            if tuples and asymmetric_pred and transitive_pred:
                strict_order.update(predicates)
            if _is_total_order(len(tuples), len(field), transitive_pred, reflexive_pred, antisymmetric_pred):
                total_order.update(predicates)
            if reflexive_pred:
                for predicate in predicates:
                    domains[("field", predicate)] = (field,)

    group_items = tuple(groups.items())
    for index, ((left_arity, left_tuples), left_predicates) in enumerate(group_items):
        for offset in range(index, len(group_items)):
            (right_arity, right_tuples), right_predicates = group_items[offset]
            if index == offset and len(left_predicates) < 2:
                continue
            equal = left_arity == right_arity and left_tuples == right_tuples
            left_implies = left_arity == right_arity and not equal and left_tuples <= right_tuples
            right_implies = left_arity == right_arity and not equal and not left_implies and right_tuples <= left_tuples
            disjoint = left_arity == right_arity and left_tuples.isdisjoint(right_tuples)
            inverted = left_arity == right_arity == 2 and left_tuples == reversed_by_predicate[right_predicates[0]]
            complement_positions = None
            if disjoint and (negated is None or any(p in negated for p in left_predicates)
                             and any(p in negated for p in right_predicates)):
                union_positions = tuple(first | second for first, second in zip(
                    positions_by_predicate[left_predicates[0]], positions_by_predicate[right_predicates[0]], strict=True,
                ))
                complement_positions = _product_positions(union_positions, len(left_tuples) + len(right_tuples))
            disjoint_args = tuple(_disjoint_position_pairs(
                positions_by_predicate[left_predicates[0]], positions_by_predicate[right_predicates[0]],
            ))
            pairs = combinations(left_predicates, 2) if index == offset else product(left_predicates, right_predicates)
            for left, right in pairs:
                ordered = (left, right) if left < right else (right, left)
                if equal:
                    equivalent.add(ordered)
                if left_implies:
                    implies.add((left, right))
                elif right_implies:
                    implies.add((right, left))
                if disjoint:
                    mutex.add(ordered)
                if inverted:
                    inverse.add(ordered)
                # A domain proof is shared; permission to negate remains per predicate.
                if complement_positions is not None and (negated is None or {left, right} <= negated):
                    complement.add(ordered)
                    domains[("complement", *ordered)] = complement_positions
                for left_arg, right_arg in disjoint_args:
                    disjoint_projection.add((left, left_arg, right, right_arg))
                    disjoint_projection.add((right, right_arg, left, left_arg))
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
    projection_positions = {**positions_by_predicate, **{
        predicate: _position_values(predicate[1], tuples) for predicate, tuples in lower_targets.items()
    }}
    _collect_projection_implications(extensions, {**extensions, **lower_targets}, project_implies, projection_positions)
    _collect_tuple_mutex(extensions, tuple_mutex)
    partitions = _partition_properties(
        extensions
        if negated is None
        else {
            predicate: tuples
            for predicate, tuples in extensions.items()
            if predicate in negated
        },
        positions_by_predicate,
    )
    for group in partitions:
        domains[("partition", group)] = tuple(frozenset().union(*(
            positions_by_predicate[predicate][index] for predicate in group
        )) for index in range(group[0][1]))
    cardinality_upper = _syntactic_properties(
        world, keys, functional, functional_set, project_implies, arg_distinct, symmetric, syntax
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
    bounded_positions = {predicate: positions_by_predicate[predicate]
                         if predicate in positions_by_predicate else _position_values(predicate[1], tuples)
                         for predicate, tuples in bounded.items()}
    positive_args, nonnegative_args = _numeric_signs(bounded_positions)
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
        domain_covers=frozenset(_domain_covers(domains, bounded_positions)),
        positive_args=positive_args,
        nonnegative_args=nonnegative_args,
    )


def _numeric_signs(
    positions: dict[Predicate, tuple[frozenset, ...]],
) -> tuple[frozenset[tuple[Predicate, int]], frozenset[tuple[Predicate, int]]]:
    positive: set[tuple[Predicate, int]] = set()
    nonnegative: set[tuple[Predicate, int]] = set()
    for predicate, arguments in positions.items():
        for index, values in enumerate(arguments):
            strictly_positive = True
            for value in values:
                if not isinstance(value, int) or value < 0:
                    break
                strictly_positive &= value > 0
            else:
                nonnegative.add((predicate, index))
                if strictly_positive:
                    positive.add((predicate, index))
    return frozenset(positive), frozenset(nonnegative)


def _syntactic_properties(
    world: ClosedWorld,
    keys: set[tuple[Predicate, tuple[int, ...]]],
    functional: set[tuple[Predicate, int, int]],
    functional_set: set[tuple[Predicate, tuple[int, ...], int]],
    project_implies: set[tuple[Predicate, Predicate, tuple[int, ...]]],
    arg_distinct: set[tuple[Predicate, int, int]],
    symmetric: set[Predicate],
    syntax: _RuleSyntax | None = None,
) -> set[tuple[Predicate, int]]:
    """Add rule-shaped properties that Clingo proves in every stable model.

    Choice rules and rule shapes suggest properties of relations whose extension
    differs between models. Syntax alone misses other definers, so each
    suggestion is kept only when no stable model violates it.
    """
    if syntax is None:
        syntax = _rule_syntax(world.program)
    rule_keys = keys | syntax.keys
    rule_functional = functional | syntax.functional
    rule_functional_set = functional_set | syntax.functional_set
    rule_arg_distinct = set(arg_distinct)
    rule_symmetric = set(symmetric)
    _collect_clause_defined_properties(
        rule_keys,
        rule_functional,
        rule_functional_set,
        rule_arg_distinct,
        rule_symmetric,
        syntax,
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
    for source, target, projection in sorted(syntax.project_implies - project_implies):
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
    for predicate, upper in sorted(syntax.cardinality):
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
    key_sets = _key_sets_by_predicate(keys)
    functional = _without_key_subsumed_functional(set(properties.functional), key_sets)
    functional_set = _without_key_subsumed_functional_set(
        set(properties.functional_set), key_sets
    )
    del key_sets
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
