from dataclasses import dataclass, fields
from typing import Literal

from ...language.asp import Predicate

# A domain-relative property is checked over a finite domain per argument
# position: the field of a reflexive or total-order relation, the product of a
# universal relation, or the union covered by a complement pair or partition.
type DomainKey = (
    tuple[Literal["field"], Predicate]
    | tuple[Literal["universal"], Predicate]
    | tuple[Literal["complement"], Predicate, Predicate]
    | tuple[Literal["partition"], tuple[Predicate, ...]]
)


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
    # (domain, position, predicate, argument): every value of the predicate
    # argument lies inside the domain position, so a variable bound there
    # ranges over values the domain-relative property was checked on.
    domain_covers: frozenset[tuple[DomainKey, int, Predicate, int]]
    # (predicate, argument): every value the closed argument takes in any model
    # is an integer > 0 (positive) or >= 0 (nonnegative).
    positive_args: frozenset[tuple[Predicate, int]]
    nonnegative_args: frozenset[tuple[Predicate, int]]

    @classmethod
    def none(cls) -> "ClosedWorldProperties":
        return cls(*(frozenset() for _field in fields(cls)))
