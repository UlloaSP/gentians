from collections.abc import Iterator, Mapping
from itertools import combinations, permutations

from ...language.asp import Predicate
from .ground_relations import GroundTerm, GroundTuple
from .properties import DomainKey

# Product and partition checks enumerate tuples; larger domains stay unproven.
MAX_PRODUCT_SIZE = 10000


def _collect_argument_properties(
    predicate: Predicate,
    tuples: frozenset[GroundTuple],
    arg_equal: set[tuple[Predicate, int, int]],
    arg_distinct: set[tuple[Predicate, int, int]],
) -> None:
    for left, right in combinations(range(predicate[1]), 2):
        if len(tuples) > 1 and all(values[left] == values[right] for values in tuples):
            arg_equal.add((predicate, left, right))
        if all(values[left] != values[right] for values in tuples):
            arg_distinct.add((predicate, left, right))


def _collect_functional_properties(
    predicate: Predicate,
    tuples: frozenset[GroundTuple],
    functional: set[tuple[Predicate, int, int]],
) -> None:
    for input_arg in range(predicate[1]):
        if len(tuples) < 2:
            continue
        for output_arg in range(predicate[1]):
            if input_arg == output_arg:
                continue
            outputs: dict[GroundTerm, GroundTerm] = {}
            valid = True
            for values in tuples:
                previous = outputs.setdefault(values[input_arg], values[output_arg])
                if previous != values[output_arg]:
                    valid = False
                    break
            if valid:
                functional.add((predicate, input_arg, output_arg))


def _collect_composite_functional_properties(
    predicate: Predicate,
    tuples: frozenset[GroundTuple],
    functional_set: set[tuple[Predicate, tuple[int, ...], int]],
) -> None:
    arity = predicate[1]
    if arity < 3 or len(tuples) < 2:
        return
    for size in range(2, arity):
        for input_args in combinations(range(arity), size):
            for output_arg in range(arity):
                if output_arg in input_args:
                    continue
                outputs: dict[GroundTuple, GroundTerm] = {}
                valid = True
                for values in tuples:
                    key = tuple(values[arg] for arg in input_args)
                    previous = outputs.setdefault(key, values[output_arg])
                    if previous != values[output_arg]:
                        valid = False
                        break
                if valid:
                    functional_set.add((predicate, input_args, output_arg))


def _without_key_subsumed_functional(
    functional: set[tuple[Predicate, int, int]],
    keys: set[tuple[Predicate, tuple[int, ...]]],
) -> set[tuple[Predicate, int, int]]:
    key_sets = _key_sets_by_predicate(keys)
    return {
        (predicate, input_arg, output_arg)
        for predicate, input_arg, output_arg in functional
        if not any(key <= {input_arg} for key in key_sets.get(predicate, ()))
    }


def _without_key_subsumed_functional_set(
    functional_set: set[tuple[Predicate, tuple[int, ...], int]],
    keys: set[tuple[Predicate, tuple[int, ...]]],
) -> set[tuple[Predicate, tuple[int, ...], int]]:
    key_sets = _key_sets_by_predicate(keys)
    return {
        (predicate, input_args, output_arg)
        for predicate, input_args, output_arg in functional_set
        if not any(key <= set(input_args) for key in key_sets.get(predicate, ()))
    }


def _without_subsumed_functional_set(
    functional_set: set[tuple[Predicate, tuple[int, ...], int]],
    functional: set[tuple[Predicate, int, int]],
) -> set[tuple[Predicate, tuple[int, ...], int]]:
    single_inputs: dict[tuple[Predicate, int], set[int]] = {}
    for predicate, input_arg, output_arg in functional:
        single_inputs.setdefault((predicate, output_arg), set()).add(input_arg)

    composite_inputs: dict[tuple[Predicate, int], list[set[int]]] = {}
    for predicate, input_args, output_arg in functional_set:
        composite_inputs.setdefault((predicate, output_arg), []).append(set(input_args))

    return {
        (predicate, input_args, output_arg)
        for predicate, input_args, output_arg in functional_set
        if not _functional_set_is_subsumed(
            predicate,
            set(input_args),
            output_arg,
            single_inputs,
            composite_inputs,
        )
    }


def _functional_set_is_subsumed(
    predicate: Predicate,
    input_args: set[int],
    output_arg: int,
    single_inputs: dict[tuple[Predicate, int], set[int]],
    composite_inputs: dict[tuple[Predicate, int], list[set[int]]],
) -> bool:
    key = (predicate, output_arg)
    if input_args & single_inputs.get(key, set()):
        return True
    return any(other < input_args for other in composite_inputs.get(key, ()))


def _without_irreflexive_subsumed_arg_distinct(
    arg_distinct: set[tuple[Predicate, int, int]],
    irreflexive_sources: set[Predicate],
) -> set[tuple[Predicate, int, int]]:
    return {
        (predicate, left, right)
        for predicate, left, right in arg_distinct
        if not (
            predicate in irreflexive_sources
            and predicate[1] == 2
            and {left, right} == {0, 1}
        )
    }


def _without_partition_subsumed_mutex(
    mutex: set[tuple[Predicate, Predicate]],
    partitions: set[tuple[Predicate, ...]],
) -> set[tuple[Predicate, Predicate]]:
    partition_pairs = {
        tuple(sorted((left, right)))
        for group in partitions
        for left, right in combinations(group, 2)
    }
    return {pair for pair in mutex if tuple(sorted(pair)) not in partition_pairs}


def _key_sets_by_predicate(
    keys: set[tuple[Predicate, tuple[int, ...]]],
) -> dict[Predicate, list[set[int]]]:
    result: dict[Predicate, list[set[int]]] = {}
    for predicate, args in keys:
        result.setdefault(predicate, []).append(set(args))
    return result


def _collect_key_properties(
    predicate: Predicate,
    tuples: frozenset[GroundTuple],
    keys: set[tuple[Predicate, tuple[int, ...]]],
) -> None:
    arity = predicate[1]
    if arity < 2 or len(tuples) < 2:
        return
    found: list[tuple[int, ...]] = []
    for size in range(1, arity):
        for args in combinations(range(arity), size):
            if any(set(existing) <= set(args) for existing in found):
                continue
            projected = {tuple(values[arg] for arg in args) for values in tuples}
            if len(projected) == len(tuples):
                found.append(args)
                keys.add((predicate, args))


def _collect_disjoint_projections(
    left: Predicate,
    left_positions: tuple[frozenset[GroundTerm], ...],
    right: Predicate,
    right_positions: tuple[frozenset[GroundTerm], ...],
    disjoint_projection: set[tuple[Predicate, int, Predicate, int]],
) -> None:
    if not left_positions or not right_positions or not all(left_positions) or not all(right_positions):
        return
    for left_arg in range(left[1]):
        left_values = left_positions[left_arg]
        for right_arg in range(right[1]):
            right_values = right_positions[right_arg]
            if left_values.isdisjoint(right_values):
                if left[1] == right[1] == 1:
                    continue
                disjoint_projection.add((left, left_arg, right, right_arg))
                disjoint_projection.add((right, right_arg, left, left_arg))


def _partition_properties(
    extensions: Mapping[Predicate, frozenset[GroundTuple]],
) -> set[tuple[Predicate, ...]]:
    """Minimal groups of pairwise disjoint relations whose union is a product.

    Every tuple of that product satisfies exactly one member, so negating all
    members of one tuple is impossible whenever each variable ranges over the
    product. Pairs are complements and are collected separately.
    """
    by_arity: dict[int, list[Predicate]] = {}
    for predicate, tuples in extensions.items():
        if tuples:
            by_arity.setdefault(predicate[1], []).append(predicate)
    partitions: set[tuple[Predicate, ...]] = set()
    for predicates in by_arity.values():
        disjoint = {
            (left, right)
            for left, right in combinations(predicates, 2)
            if extensions[left].isdisjoint(extensions[right])
        }
        for size in range(3, min(len(predicates), 6) + 1):
            for group in combinations(predicates, size):
                if any(pair not in disjoint for pair in combinations(group, 2)):
                    continue
                if any(set(other) < set(group) for other in partitions):
                    continue
                union = frozenset().union(*(extensions[member] for member in group))
                if _product_positions(group[0], union) is not None:
                    partitions.add(group)
    return partitions


def _position_values(
    arity: int, tuples: frozenset[GroundTuple]
) -> tuple[frozenset[GroundTerm], ...]:
    return tuple(frozenset(values[index] for values in tuples) for index in range(arity))


def _product_positions(
    predicate: Predicate, tuples: frozenset[GroundTuple]
) -> tuple[frozenset[GroundTerm], ...] | None:
    """Per-position values when the tuples are exactly their product."""
    if not tuples:
        return None
    positions = _position_values(predicate[1], tuples)
    size = 1
    for values in positions:
        size *= len(values)
    if size != len(tuples) or size > MAX_PRODUCT_SIZE:
        return None
    return positions


def _domain_covers(
    domains: Mapping[DomainKey, tuple[frozenset[GroundTerm], ...]],
    extensions: Mapping[Predicate, frozenset[GroundTuple]],
) -> Iterator[tuple[DomainKey, int, Predicate, int]]:
    """Arguments whose values all lie inside one position of a domain."""
    arguments = {
        (predicate, index): frozenset(values[index] for values in tuples)
        for predicate, tuples in extensions.items()
        for index in range(predicate[1])
    }
    for key, positions in domains.items():
        for position, domain in enumerate(positions):
            for (predicate, index), values in arguments.items():
                if values <= domain:
                    yield key, position, predicate, index


def _collect_tuple_mutex(
    extensions: Mapping[Predicate, frozenset[GroundTuple]],
    tuple_mutex: set[tuple[Predicate, Predicate, tuple[int, ...]]],
) -> None:
    relations = {
        predicate: tuples
        for predicate, tuples in extensions.items()
        if predicate[1] > 1
    }
    by_arity: dict[int, list[tuple[Predicate, frozenset[GroundTuple]]]] = {}
    for predicate, tuples in relations.items():
        by_arity.setdefault(predicate[1], []).append((predicate, tuples))
    for left, left_tuples in relations.items():
        identity = tuple(range(left[1]))
        for projection in permutations(identity):
            if projection == identity:
                continue
            projected = {tuple(values[arg] for arg in projection) for values in left_tuples}
            for right, right_tuples in by_arity[left[1]]:
                if projected.isdisjoint(right_tuples):
                    tuple_mutex.add((left, right, projection))


def _collect_projection_implications(
    sources: Mapping[Predicate, frozenset[GroundTuple]],
    targets: Mapping[Predicate, frozenset[GroundTuple]],
    project_implies: set[tuple[Predicate, Predicate, tuple[int, ...]]],
) -> None:
    by_arity: dict[int, list[tuple[Predicate, frozenset[GroundTuple]]]] = {}
    for target, tuples in targets.items():
        if tuples:
            by_arity.setdefault(target[1], []).append((target, tuples))
    for source, tuples in sources.items():
        for arity, candidates in by_arity.items():
            if source[1] <= arity:
                continue
            for projection in permutations(range(source[1]), arity):
                projected = {tuple(values[arg] for arg in projection) for values in tuples}
                for target, target_tuples in candidates:
                    if projected <= target_tuples:
                        project_implies.add((source, target, projection))


def _is_transitive(tuples: frozenset[GroundTuple]) -> bool:
    if len(tuples) < 3:
        return False
    successors: dict[GroundTerm, set[GroundTerm]] = {}
    for left, right in tuples:
        successors.setdefault(left, set()).add(right)
    for left, middle in tuples:
        following = successors.get(middle)
        if following is not None and not following <= successors[left]:
            return False
    return True


def _is_reflexive(tuples: frozenset[GroundTuple]) -> bool:
    domain = {value for row in tuples for value in row}
    return bool(domain) and all((value, value) in tuples for value in domain)


def _is_total_order(tuples: frozenset[GroundTuple], transitive: bool, reflexive: bool) -> bool:
    domain = {value for row in tuples for value in row}
    if (
        len(domain) < 2
        or not reflexive
        or not transitive
        or any(left != right and (right, left) in tuples for left, right in tuples)
    ):
        return False
    for left, right in permutations(domain, 2):
        if (left, right) not in tuples and (right, left) not in tuples:
            return False
    return True


def _is_acyclic(tuples: frozenset[GroundTuple]) -> bool:
    graph: dict[GroundTerm, set[GroundTerm]] = {}
    for left, right in tuples:
        graph.setdefault(left, set()).add(right)
        graph.setdefault(right, set())
    visiting: set[GroundTerm] = set()
    visited: set[GroundTerm] = set()

    def visit(node: GroundTerm) -> bool:
        if node in visiting:
            return False
        if node in visited:
            return True
        visiting.add(node)
        for next_node in graph[node]:
            if not visit(next_node):
                return False
        visiting.remove(node)
        visited.add(node)
        return True

    return bool(tuples) and all(visit(node) for node in graph)
