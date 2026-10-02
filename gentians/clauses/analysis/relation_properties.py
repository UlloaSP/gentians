from collections.abc import Iterator, Mapping
from heapq import nlargest
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
        remaining = iter(tuples)
        first = next(remaining, None)
        if first is None:
            arg_distinct.add((predicate, left, right))
        elif first[left] == first[right]:
            if len(tuples) > 1 and all(values[left] == values[right] for values in remaining):
                arg_equal.add((predicate, left, right))
        elif all(values[left] != values[right] for values in remaining):
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
            has_key = bool(found_keys) and any(key <= inputs for key in found_keys)
            groups: dict[GroundTuple, GroundTuple] = {}
            if not has_key:
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
            if not has_key and len(groups) == len(tuples):
                keys.add((predicate, input_args))
                found_keys.append(inputs)


def _without_key_subsumed_functional(
    functional: set[tuple[Predicate, int, int]],
    key_sets: Mapping[Predicate, list[set[int]]],
) -> set[tuple[Predicate, int, int]]:
    result = set()
    for item in functional:
        predicate, input_arg, _output_arg = item
        inputs = {input_arg}
        if not any(key <= inputs for key in key_sets.get(predicate, ())):
            result.add(item)
    return result


def _without_key_subsumed_functional_set(
    functional_set: set[tuple[Predicate, tuple[int, ...], int]],
    key_sets: Mapping[Predicate, list[set[int]]],
) -> set[tuple[Predicate, tuple[int, ...], int]]:
    result = set()
    for item in functional_set:
        predicate, input_args, _output_arg = item
        inputs = set(input_args)
        if not any(key <= inputs for key in key_sets.get(predicate, ())):
            result.add(item)
    return result


def _without_subsumed_functional_set(
    functional_set: set[tuple[Predicate, tuple[int, ...], int]],
    functional: set[tuple[Predicate, int, int]],
) -> set[tuple[Predicate, tuple[int, ...], int]]:
    single_inputs: dict[tuple[Predicate, int], set[int]] = {}
    for predicate, input_arg, output_arg in functional:
        single_inputs.setdefault((predicate, output_arg), set()).add(input_arg)

    groups: dict[tuple[Predicate, int], dict[frozenset[int], list[tuple[Predicate, tuple[int, ...], int]]]] = {}
    for item in functional_set:
        predicate, inputs, output = item
        groups.setdefault((predicate, output), {}).setdefault(frozenset(inputs), []).append(item)
    result = set()
    for key, determinants in groups.items():
        minimal: list[frozenset[int]] = []
        singles = single_inputs.get(key, set())
        for inputs in sorted(determinants, key=len):
            if inputs & singles or any(other < inputs for other in minimal):
                continue
            minimal.append(inputs)
            result.update(determinants[inputs])
    return result


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


def _disjoint_position_pairs(
    left_positions: tuple[frozenset[GroundTerm], ...],
    right_positions: tuple[frozenset[GroundTerm], ...],
) -> Iterator[tuple[int, int]]:
    if not left_positions or not right_positions or not all(left_positions) or not all(right_positions):
        return
    if len(left_positions) == len(right_positions) == 1:
        return
    for left_arg, left_values in enumerate(left_positions):
        for right_arg, right_values in enumerate(right_positions):
            if left_values.isdisjoint(right_values):
                yield left_arg, right_arg


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
    counts = {predicate: len(tuples) for predicate, tuples in extensions.items()}
    for predicates in by_arity.values():
        uniform_count = counts[predicates[0]]
        uniform = all(counts[predicate] == uniform_count for predicate in predicates)
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
                if not remaining:
                    if product_size == count and product_size <= MAX_PRODUCT_SIZE:
                        partitions.add(group)
                        minimal.append(frozenset(group))
                    continue
                # Domains only grow. Even the largest remaining disjoint
                # relations cannot complete a product larger than their tuples.
                capacity = count + (remaining * uniform_count if uniform else
                    sum(nlargest(remaining, (counts[predicate] for predicate in candidates))))
                if product_size > min(capacity, MAX_PRODUCT_SIZE):
                    continue
                for index in reversed(range(len(candidates) - remaining + 1)):
                    member = candidates[index]
                    pending.append((
                        (*group, member),
                        tuple(candidate for candidate in candidates[index + 1:] if candidate in following[member]),
                        count + counts[member],
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
    if not domains:
        return
    arguments = tuple(
        (predicate, index, values)
        for predicate, positions in positions_by_predicate.items()
        for index, values in enumerate(positions)
    )
    columns: dict[frozenset[GroundTerm], list[int]] = {}
    for index, (_predicate, _argument, values) in enumerate(arguments):
        columns.setdefault(values, []).append(index)
    matches: dict[frozenset[GroundTerm], tuple[tuple[Predicate, int], ...]] = {}
    for key, positions in domains.items():
        for position, domain in enumerate(positions):
            compatible = matches.get(domain)
            if compatible is None:
                included = sorted(index for column, indexes in columns.items() if column <= domain for index in indexes)
                compatible = tuple((arguments[index][0], arguments[index][1]) for index in included)
                matches[domain] = compatible
            for predicate, index in compatible:
                yield key, position, predicate, index


def _collect_tuple_mutex(
    extensions: Mapping[Predicate, frozenset[GroundTuple]],
    tuple_mutex: set[tuple[Predicate, Predicate, tuple[int, ...]]],
) -> None:
    by_arity: dict[int, dict[frozenset[GroundTuple], list[Predicate]]] = {}
    for predicate, tuples in extensions.items():
        if predicate[1] > 1:
            by_arity.setdefault(predicate[1], {}).setdefault(tuples, []).append(predicate)
    for arity, groups in by_arity.items():
        identity = tuple(range(arity))
        for left_tuples, left_predicates in groups.items():
            for projection in permutations(identity):
                if projection == identity:
                    continue
                projected = {tuple(values[arg] for arg in projection) for values in left_tuples}
                for right_tuples, right_predicates in groups.items():
                    if projected.isdisjoint(right_tuples):
                        if len(left_predicates) == len(right_predicates) == 1:
                            tuple_mutex.add((left_predicates[0], right_predicates[0], projection))
                        else:
                            tuple_mutex.update(
                                (left, right, projection)
                                for left in left_predicates for right in right_predicates
                            )


def _collect_projection_implications(
    sources: Mapping[Predicate, frozenset[GroundTuple]],
    targets: Mapping[Predicate, frozenset[GroundTuple]],
    project_implies: set[tuple[Predicate, Predicate, tuple[int, ...]]],
    positions: Mapping[Predicate, tuple[frozenset[GroundTerm], ...]],
) -> None:
    target_groups: dict[int, dict[frozenset[GroundTuple], list[Predicate]]] = {}
    for target, tuples in targets.items():
        if tuples:
            target_groups.setdefault(target[1], {}).setdefault(tuples, []).append(target)
    by_arity = {arity: tuple(groups.items()) for arity, groups in target_groups.items()}
    source_groups: dict[tuple[int, frozenset[GroundTuple]], list[Predicate]] = {}
    for source, tuples in sources.items():
        source_groups.setdefault((source[1], tuples), []).append(source)
    for (source_arity, tuples), source_predicates in source_groups.items():
        source_positions = positions[source_predicates[0]]
        for arity, candidates in by_arity.items():
            if source_arity <= arity:
                continue
            # Retain tuple inclusion as the proof. Position domains only rule
            # out impossible mappings before their Cartesian/permutation work.
            alternatives = tuple(tuple(frozenset(
                    index for index, values in enumerate(source_positions) if values <= domain
                ) for domain in positions[aliases[0]]) for _tuples, aliases in candidates)
            for projection, matches in _projection_matches(alternatives, arity):
                if len(matches) == 1:
                    target_tuples, target_predicates = candidates[matches[0]]
                    if all(tuple(values[arg] for arg in projection) in target_tuples for values in tuples):
                        project_implies.update((source, target, projection)
                                              for source in source_predicates for target in target_predicates)
                    continue
                projected = {tuple(values[arg] for arg in projection) for values in tuples}
                for index in matches:
                    target_tuples, target_predicates = candidates[index]
                    if projected <= target_tuples:
                        project_implies.update((source, target, projection)
                                              for source in source_predicates for target in target_predicates)


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


def _binary_successors(tuples: frozenset[GroundTuple]) -> dict[GroundTerm, set[GroundTerm]]:
    successors: dict[GroundTerm, set[GroundTerm]] = {}
    for left, right in tuples:
        successors.setdefault(left, set()).add(right)
    return successors


def _is_transitive(successors: Mapping[GroundTerm, set[GroundTerm]], tuple_count: int) -> bool:
    if tuple_count < 3:
        return False
    for following in successors.values():
        for middle in following:
            following_middle = successors.get(middle)
            if following_middle is not None and not following_middle <= following:
                return False
    return True


def _is_reflexive(tuples: frozenset[GroundTuple], domain: frozenset[GroundTerm]) -> bool:
    return bool(domain) and all((value, value) in tuples for value in domain)


def _is_total_order(
    tuple_count: int, domain_size: int, transitive: bool, reflexive: bool, antisymmetric: bool,
) -> bool:
    # Reflexivity supplies every diagonal. Antisymmetry allows at most one edge
    # per unordered pair, so this cardinality proves comparability of all pairs.
    return (domain_size >= 2 and transitive and reflexive and antisymmetric
            and tuple_count == domain_size * (domain_size + 1) // 2)


def _is_acyclic(successors: Mapping[GroundTerm, set[GroundTerm]]) -> bool:
    incoming: dict[GroundTerm, int] = {}
    for left, following in successors.items():
        incoming.setdefault(left, 0)
        for right in following:
            incoming[right] = incoming.get(right, 0) + 1
    pending = [node for node, count in incoming.items() if not count]
    visited = 0
    while pending:
        node = pending.pop()
        visited += 1
        for successor in successors.get(node, ()):
            incoming[successor] -= 1
            if not incoming[successor]:
                pending.append(successor)
    return bool(successors) and visited == len(incoming)
