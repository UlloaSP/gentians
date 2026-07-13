from dataclasses import dataclass

from .parser import Predicate


@dataclass(frozen=True, slots=True)
class ClosedWorldProperties:
    symmetric: frozenset[Predicate]
    asymmetric: frozenset[Predicate]
    antisymmetric: frozenset[Predicate]
    acyclic: frozenset[Predicate]
    reflexive: frozenset[Predicate]
    strict_order: frozenset[Predicate]
    total_order: frozenset[Predicate]
    inverse: frozenset[tuple[Predicate, Predicate]]
    implies: frozenset[tuple[Predicate, Predicate]]
    equivalent: frozenset[tuple[Predicate, Predicate]]
    project_implies: frozenset[
        tuple[Predicate, Predicate, tuple[int, ...]]
    ]
    disjoint_projection: frozenset[tuple[Predicate, int, Predicate, int]]
    tuple_mutex: frozenset[tuple[Predicate, Predicate, tuple[int, ...]]]
    mutex: frozenset[tuple[Predicate, Predicate]]
    complement: frozenset[tuple[Predicate, Predicate]]
    partitions: frozenset[tuple[Predicate, ...]]
    universal: frozenset[Predicate]
    empty: frozenset[Predicate]
    arg_equal: frozenset[tuple[Predicate, int, int]]
    arg_distinct: frozenset[tuple[Predicate, int, int]]
    functional: frozenset[tuple[Predicate, int, int]]
    functional_set: frozenset[tuple[Predicate, tuple[int, ...], int]]
    keys: frozenset[tuple[Predicate, tuple[int, ...]]]
    cardinality_upper: frozenset[tuple[Predicate, int]]
    transitive: frozenset[Predicate]
