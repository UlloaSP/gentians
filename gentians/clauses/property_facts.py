from ..language.asp import Predicate
from .analysis.properties import ClosedWorldProperties, DomainKey
from .clause_mode import ClauseMode
from .property_consumers import PropertyMaps


def compile_property_facts(
    properties: ClosedWorldProperties,
    predicate_ids: dict[Predicate, int],
    modes: list[ClauseMode] | None = None,
    maps: PropertyMaps | None = None,
) -> list[str]:
    parts: list[str] = []

    def pred_id(predicate: Predicate) -> int | None:
        return predicate_ids.get(predicate)

    # Property consumers here join positive plain body atoms. Unknown shapes
    # retain the map; flattened bindings must not be mistaken for term indexes.
    if maps is None and modes is not None:
        maps = PropertyMaps(modes)

    def compatible(left: Predicate, right: Predicate, projection: tuple[tuple[int, int], ...]) -> bool:
        if maps is None:
            return True
        return maps.compatible(left, right, projection)

    for predicate in sorted(properties.symmetric):
        if (identifier := pred_id(predicate)) is not None:
            parts.append(f"symmetric_pred({identifier}).")
    for predicate in sorted(properties.asymmetric):
        if (identifier := pred_id(predicate)) is not None:
            parts.append(f"asymmetric_pred({identifier}).")
    for predicate in sorted(properties.antisymmetric):
        if (identifier := pred_id(predicate)) is not None:
            parts.append(f"antisymmetric_pred({identifier}).")
    for predicate in sorted(properties.acyclic):
        if (identifier := pred_id(predicate)) is not None:
            parts.append(f"acyclic_pred({identifier}).")
    for predicate in sorted(properties.reflexive):
        if (identifier := pred_id(predicate)) is not None:
            parts.append(f"reflexive_pred({identifier}).")
    for predicate in sorted(properties.strict_order):
        if (identifier := pred_id(predicate)) is not None:
            parts.append(f"strict_order_pred({identifier}).")
    for predicate in sorted(properties.total_order):
        if (identifier := pred_id(predicate)) is not None:
            parts.append(f"total_order_pred({identifier}).")
    for predicate in sorted(properties.universal):
        if (identifier := pred_id(predicate)) is not None:
            parts.append(f"universal_pred({identifier}).")
    for predicate in sorted(properties.empty):
        if (identifier := pred_id(predicate)) is not None:
            parts.append(f"empty_pred({identifier}).")
    for left, right in sorted(properties.inverse):
        left_id = pred_id(left)
        right_id = pred_id(right)
        if left_id is not None and right_id is not None:
            parts.append(f"inverse_pred({left_id},{right_id}).")
    for left, right in sorted(properties.implies):
        left_id = pred_id(left)
        right_id = pred_id(right)
        if left_id is not None and right_id is not None:
            parts.append(f"implies_pred({left_id},{right_id}).")
    for left, right in sorted(properties.equivalent):
        left_id = pred_id(left)
        right_id = pred_id(right)
        if left_id is not None and right_id is not None:
            parts.append(f"equivalent_pred({left_id},{right_id}).")
    projection_id = 0
    for source, target, projection in sorted(properties.project_implies):
        source_id = pred_id(source)
        target_id = pred_id(target)
        if source_id is None or target_id is None:
            continue
        parts.append(f"project_implies_pred({source_id},{target_id},{projection_id}).")
        parts.extend(
            f"project_arg({projection_id},{target_arg},{source_arg})."
            for target_arg, source_arg in enumerate(projection)
        )
        projection_id += 1
    for left, left_arg, right, right_arg in sorted(properties.disjoint_projection):
        left_id = pred_id(left)
        right_id = pred_id(right)
        if left_id is not None and right_id is not None and compatible(left, right, ((left_arg, right_arg),)):
            parts.append(f"disjoint_arg({left_id},{left_arg},{right_id},{right_arg}).")
    # The mapping describes positions, not predicate membership. Share equal
    # complete mappings while retaining every signed predicate pair below.
    tuple_mutex_projections: dict[tuple[int, ...], int] = {}
    for left, right, projection in sorted(properties.tuple_mutex):
        left_id = pred_id(left)
        right_id = pred_id(right)
        if left_id is None or right_id is None:
            continue
        if not compatible(left, right, tuple((source, target) for target, source in enumerate(projection))):
            continue
        tuple_mutex_id = tuple_mutex_projections.get(projection)
        if tuple_mutex_id is None:
            tuple_mutex_id = len(tuple_mutex_projections)
            tuple_mutex_projections[projection] = tuple_mutex_id
            parts.extend(
                f"tuple_mutex_arg({tuple_mutex_id},{right_arg},{left_arg})."
                for right_arg, left_arg in enumerate(projection)
            )
        parts.append(f"tuple_mutex_pred({left_id},{right_id},{tuple_mutex_id}).")
    for left, right in sorted(properties.mutex):
        left_id = pred_id(left)
        right_id = pred_id(right)
        if left_id is not None and right_id is not None:
            parts.append(f"mutex_pred({left_id},{right_id}).")
    for left, right in sorted(properties.complement):
        left_id = pred_id(left)
        right_id = pred_id(right)
        if left_id is not None and right_id is not None:
            parts.append(f"complement_pred({left_id},{right_id}).")
    partition_ids: dict[tuple[Predicate, ...], int] = {}
    for group in sorted(properties.partitions):
        ids = [pred_id(predicate) for predicate in group]
        if any(identifier is None for identifier in ids):
            continue
        partition_ids[group] = len(partition_ids)
        parts.extend(
            f"partition_pred({partition_ids[group]},{identifier})." for identifier in ids
        )

    def domain_term(key: DomainKey) -> str | None:
        match key:
            case ("partition", group):
                return f"partition({partition_ids[group]})" if group in partition_ids else None
            case ("complement", left, right):
                left_id, right_id = pred_id(left), pred_id(right)
                if left_id is None or right_id is None:
                    return None
                return f"complement({left_id},{right_id})"
            case (kind, predicate):
                identifier = pred_id(predicate)
                return None if identifier is None else f"{kind}({identifier})"

    for key, position, predicate, argument in sorted(properties.domain_covers, key=repr):
        term = domain_term(key)
        if term is not None and (identifier := pred_id(predicate)) is not None:
            parts.append(f"domain_cover({term},{position},{identifier},{argument}).")
    for predicate, left, right in sorted(properties.arg_equal):
        if (identifier := pred_id(predicate)) is not None:
            parts.append(f"arg_equal_pred({identifier},{left},{right}).")
    for predicate, left, right in sorted(properties.arg_distinct):
        if (identifier := pred_id(predicate)) is not None:
            parts.append(f"arg_distinct_pred({identifier},{left},{right}).")
    for predicate, input_arg, output_arg in sorted(properties.functional):
        if (identifier := pred_id(predicate)) is not None:
            parts.append(f"functional_pred({identifier},{input_arg},{output_arg}).")
    fd_id = 0
    for predicate, input_args, output_arg in sorted(properties.functional_set):
        if (identifier := pred_id(predicate)) is None:
            continue
        parts.append(f"functional_set_pred({identifier},{fd_id},{output_arg}).")
        parts.extend(f"functional_set_arg({fd_id},{arg})." for arg in input_args)
        fd_id += 1
    key_id = 0
    for predicate, args in sorted(properties.keys):
        if (identifier := pred_id(predicate)) is None:
            continue
        parts.append(f"key_pred({identifier},{key_id}).")
        parts.extend(f"key_arg({key_id},{arg})." for arg in args)
        key_id += 1
    for predicate, upper in sorted(properties.cardinality_upper):
        if (identifier := pred_id(predicate)) is not None:
            parts.append(f"cardinality_upper_pred({identifier},{upper}).")
    for predicate in sorted(properties.transitive):
        if (identifier := pred_id(predicate)) is not None:
            parts.append(f"transitive_pred({identifier}).")
    for predicate, argument in sorted(properties.positive_args):
        if (identifier := pred_id(predicate)) is not None:
            parts.append(f"positive_arg({identifier},{argument}).")
    for predicate, argument in sorted(properties.nonnegative_args):
        if (identifier := pred_id(predicate)) is not None:
            parts.append(f"nonnegative_arg({identifier},{argument}).")
    return parts
