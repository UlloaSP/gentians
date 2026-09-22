from itertools import combinations, permutations

from ...language.asp import Predicate
from .ground_relations import GroundTerm, GroundTuple


def _collect_argument_properties(
    predicate: Predicate,
    tuples: set[GroundTuple],
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
    tuples: set[GroundTuple],
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
    tuples: set[GroundTuple],
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
    tuples: set[GroundTuple],
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
    left_tuples: set[GroundTuple],
    right: Predicate,
    right_tuples: set[GroundTuple],
    disjoint_projection: set[tuple[Predicate, int, Predicate, int]],
) -> None:
    if not left_tuples or not right_tuples:
        return
    for left_arg in range(left[1]):
        left_values = {values[left_arg] for values in left_tuples}
        for right_arg in range(right[1]):
            right_values = {values[right_arg] for values in right_tuples}
            if left_values.isdisjoint(right_values):
                if left[1] == right[1] == 1:
                    continue
                disjoint_projection.add((left, left_arg, right, right_arg))
                disjoint_projection.add((right, right_arg, left, left_arg))


def _partition_properties(
    extensions: dict[Predicate, set[GroundTuple]],
    tuple_universe_by_arity: dict[int, set[GroundTuple]],
) -> set[tuple[Predicate, ...]]:
    partitions: set[tuple[Predicate, ...]] = set()
    for arity, universe in tuple_universe_by_arity.items():
        predicates = [
            predicate
            for predicate, tuples in extensions.items()
            if predicate[1] == arity and tuples and tuples < universe
        ]
        for size in range(3, min(len(predicates), 6) + 1):
            for group in combinations(predicates, size):
                covered: set[GroundTuple] = set()
                valid = True
                for predicate in group:
                    tuples = extensions[predicate]
                    if covered & tuples:
                        valid = False
                        break
                    covered.update(tuples)
                if valid and covered == universe:
                    partitions.add(tuple(sorted(group)))
    return {
        group
        for group in partitions
        if not any(set(other) < set(group) for other in partitions)
    }


def _collect_tuple_mutex(
    extensions: dict[Predicate, set[GroundTuple]],
    closed_body_predicates: set[Predicate],
    tuple_mutex: set[tuple[Predicate, Predicate, tuple[int, ...]]],
) -> None:
    closed_extensions = {
        predicate: tuples
        for predicate, tuples in extensions.items()
        if predicate in closed_body_predicates and predicate[1] > 1
    }
    for left, left_tuples in closed_extensions.items():
        for right, right_tuples in closed_extensions.items():
            if left[1] != right[1]:
                continue
            for projection in permutations(range(left[1])):
                if projection == tuple(range(left[1])):
                    continue
                projected = {
                    tuple(values[arg] for arg in projection) for values in left_tuples
                }
                if projected.isdisjoint(right_tuples):
                    tuple_mutex.add((left, right, projection))


def _collect_projection_implications(
    source: Predicate,
    source_tuples: set[GroundTuple],
    target: Predicate,
    target_tuples: set[GroundTuple],
    project_implies: set[tuple[Predicate, Predicate, tuple[int, ...]]],
) -> None:
    if source[1] <= target[1] or not target_tuples:
        return
    for projection in permutations(range(source[1]), target[1]):
        projected = {
            tuple(values[arg] for arg in projection) for values in source_tuples
        }
        if projected <= target_tuples:
            project_implies.add((source, target, projection))


def _is_transitive(tuples: set[GroundTuple]) -> bool:
    if len(tuples) < 3:
        return False
    for left, middle in tuples:
        for other_middle, right in tuples:
            if middle == other_middle and (left, right) not in tuples:
                return False
    return True


def _is_reflexive(tuples: set[GroundTuple]) -> bool:
    domain = {value for row in tuples for value in row}
    return bool(domain) and all((value, value) in tuples for value in domain)


def _is_total_order(tuples: set[GroundTuple]) -> bool:
    domain = {value for row in tuples for value in row}
    if (
        len(domain) < 2
        or not _is_reflexive(tuples)
        or not _is_transitive(tuples)
        or any(left != right and (right, left) in tuples for left, right in tuples)
    ):
        return False
    for left, right in permutations(domain, 2):
        if (left, right) not in tuples and (right, left) not in tuples:
            return False
    return True


def _is_acyclic(tuples: set[GroundTuple]) -> bool:
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
