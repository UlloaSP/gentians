from collections.abc import Iterator, Mapping
from itertools import combinations, permutations
from math import prod

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


def _collect_dependency_properties(
    predicate: Predicate,
    tuples: frozenset[GroundTuple],
    functional: set[tuple[Predicate, int, int]],
    functional_set: set[tuple[Predicate, tuple[int, ...], int]],
    keys: set[tuple[Predicate, tuple[int, ...]]],
) -> None:
    """Group each determinant once, sharing the scan across outputs and keys."""
    arity = predicate[1]
    if arity < 2 or len(tuples) < 2:
        return
    found_keys: list[frozenset[int]] = []
    for size in range(1, arity):
        for input_args in combinations(range(arity), size):
            inputs = frozenset(input_args)
            valid = set(range(arity)) - inputs
            groups: dict[GroundTuple, GroundTuple] = {}
            for values in tuples:
                key = tuple(values[arg] for arg in input_args)
                previous = groups.setdefault(key, values)
                if previous is not values:
                    valid.difference_update(arg for arg in tuple(valid) if previous[arg] != values[arg])
                    if not valid:
                        break
            for output_arg in valid:
                if size == 1:
                    functional.add((predicate, input_args[0], output_arg))
                else:
                    functional_set.add((predicate, input_args, output_arg))
            if len(groups) == len(tuples) and not any(key <= inputs for key in found_keys):
                keys.add((predicate, input_args))
                found_keys.append(inputs)


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
    positions: Mapping[Predicate, tuple[frozenset[GroundTerm], ...]],
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
        following = {left: frozenset(
            right for right in predicates[index + 1:]
            if extensions[left].isdisjoint(extensions[right])
        ) for index, left in enumerate(predicates)}
        minimal: list[frozenset[Predicate]] = []
        for size in range(3, min(len(predicates), 6) + 1):
            pending: list[tuple[tuple[Predicate, ...], tuple[Predicate, ...], int, tuple[frozenset[GroundTerm], ...]]] = [
                ((), tuple(predicates), 0, tuple(frozenset() for _ in range(predicates[0][1])))
            ]
            while pending:
                group, candidates, count, domains = pending.pop()
                remaining = size - len(group)
                if len(candidates) < remaining or any(other <= frozenset(group) for other in minimal):
                    continue
                product_size = prod(map(len, domains))
                # Domains only grow. Even the largest remaining disjoint
                # relations cannot complete a product larger than their tuples.
                capacity = count + sum(sorted((len(extensions[predicate]) for predicate in candidates), reverse=True)[:remaining])
                if product_size > min(capacity, MAX_PRODUCT_SIZE):
                    continue
                if not remaining:
                    if product_size == count:
                        partitions.add(group)
                        minimal.append(frozenset(group))
                    continue
                for index in reversed(range(len(candidates) - remaining + 1)):
                    member = candidates[index]
                    pending.append((
                        (*group, member),
                        tuple(candidate for candidate in candidates[index + 1:] if candidate in following[member]),
                        count + len(extensions[member]),
                        tuple(left | right for left, right in zip(domains, positions[member], strict=True)),
                    ))
    return partitions


def _position_values(
    arity: int, tuples: frozenset[GroundTuple]
) -> tuple[frozenset[GroundTerm], ...]:
    return tuple(frozenset(values[index] for values in tuples) for index in range(arity))


def _product_positions(
    positions: tuple[frozenset[GroundTerm], ...], tuple_count: int,
) -> tuple[frozenset[GroundTerm], ...] | None:
    """Per-position values when the tuples are exactly their product."""
    if not tuple_count:
        return None
    size = prod(map(len, positions))
    if size != tuple_count or size > MAX_PRODUCT_SIZE:
        return None
    return positions


def _domain_covers(
    domains: Mapping[DomainKey, tuple[frozenset[GroundTerm], ...]],
    positions_by_predicate: Mapping[Predicate, tuple[frozenset[GroundTerm], ...]],
) -> Iterator[tuple[DomainKey, int, Predicate, int]]:
    """Arguments whose values all lie inside one position of a domain."""
    arguments = {
        (predicate, index): values
        for predicate, positions in positions_by_predicate.items()
        for index, values in enumerate(positions)
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
    positions: Mapping[Predicate, tuple[frozenset[GroundTerm], ...]],
) -> None:
    by_arity: dict[int, list[tuple[Predicate, frozenset[GroundTuple]]]] = {}
    for target, tuples in targets.items():
        if tuples:
            by_arity.setdefault(target[1], []).append((target, tuples))
    for source, tuples in sources.items():
        source_positions = positions[source]
        for arity, candidates in by_arity.items():
            if source[1] <= arity:
                continue
            # Retain tuple inclusion as the proof. Position domains only rule
            # out impossible mappings before their Cartesian/permutation work.
            alternatives = tuple(tuple(frozenset(
                    index for index, values in enumerate(source_positions) if values <= domain
                ) for domain in positions[target]) for target, _tuples in candidates)
            for projection, matches in _projection_matches(alternatives, arity):
                projected = {tuple(values[arg] for arg in projection) for values in tuples}
                for index in matches:
                    target, target_tuples = candidates[index]
                    if projected <= target_tuples:
                        project_implies.add((source, target, projection))


def _projection_matches(
    alternatives: tuple[tuple[frozenset[int], ...], ...], arity: int,
) -> Iterator[tuple[tuple[int, ...], tuple[int, ...]]]:
    """Stream injective mappings, retaining only targets compatible with a prefix."""
    choices = alternatives[0][0] if arity else frozenset()
    if all(allowed == choices for target in alternatives for allowed in target):
        # Uniform domains cannot reject a prefix. Let itertools enumerate the
        # mappings without rebuilding candidate sets at every depth.
        matches = tuple(range(len(alternatives)))
        for projection in permutations(sorted(choices), arity):
            yield projection, matches
        return
    pending: list[tuple[tuple[int, ...], tuple[int, ...]]] = [((), tuple(range(len(alternatives))))]
    while pending:
        selected, matches = pending.pop()
        if len(selected) == arity:
            yield selected, matches
            continue
        choices = frozenset().union(*(alternatives[index][len(selected)] for index in matches)) - frozenset(selected)
        for value in sorted(choices, reverse=True):
            pending.append(((*selected, value), tuple(
                index for index in matches if value in alternatives[index][len(selected)]
            )))


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
    graph: dict[GroundTerm, list[GroundTerm]] = {}
    incoming: dict[GroundTerm, int] = {}
    for left, right in tuples:
        graph.setdefault(left, []).append(right)
        incoming.setdefault(left, 0)
        incoming[right] = incoming.get(right, 0) + 1
    pending = [node for node, count in incoming.items() if not count]
    visited = 0
    while pending:
        node = pending.pop()
        visited += 1
        for successor in graph.get(node, ()):
            incoming[successor] -= 1
            if not incoming[successor]:
                pending.append(successor)
    return bool(tuples) and visited == len(incoming)
