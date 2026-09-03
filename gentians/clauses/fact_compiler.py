from collections import Counter

import clingo

from ..language.ir.aggregate_literal import AggregateLiteral
from ..language.ir.arithmetic_literal import ArithmeticLiteral
from ..language.ir.atom_literal import AtomLiteral
from .closed_world_properties import ClosedWorldProperties
from ..language.ir.comparison_literal import ComparisonLiteral
from ..language.ir.conditional_literal import ConditionalLiteral
from .clause_mode import ClauseMode
from ..language.asp import (
    Predicate,
)
from ..language.ir.inductive_task import InductiveTask
from .extensions import _numeric_domain_values
from .mode_compiler import _binding_positions, _closed_body_predicates
from .properties import _closed_world_properties
from .task_analysis import _closed_world_nodes, _closed_world_program

def _facts(
    task: InductiveTask,
    modes: list[ClauseMode],
    predicate_arg_types: dict[tuple[str, int, int], str],
    max_variables: int,
    max_head_literals: int,
    max_body_literals: int,
) -> str:
    nodes = _closed_world_nodes(task)
    properties = _closed_world_properties(
        nodes,
        predicate_arg_types,
        _closed_body_predicates(task),
        _closed_world_program(task),
    )
    predicate_ids = _predicate_ids(modes)
    structured_predicates = {
        mode.literal.atom.signature
        for mode in modes
        if isinstance(mode.literal, AtomLiteral)
        and any(term.kind in {"function", "tuple"} for term in mode.literal.atom.terms)
    }
    aggregate_modes = [
        (mode, mode.literal)
        for mode in modes
        if isinstance(mode.literal, AggregateLiteral)
    ]
    aggregate_has_shorter_mode: set[int] = set()
    for mode, aggregate in aggregate_modes:
        if any(
            other.function == aggregate.function
            and other.conditions == aggregate.conditions
            and len(other.tuple_terms) == len(aggregate.tuple_terms) - 1
            for _other_mode, other in aggregate_modes
        ):
            aggregate_has_shorter_mode.add(mode.id)
    parts = [
        f"max_body({max_body_literals}).",
        f"max_head({max_head_literals}).",
        f"max_vars({max_variables}).",
    ]
    parts.extend(
        f"condition_group_recall({group},{max_body_literals if mode.recall < 0 else mode.recall})."
        for group, mode in enumerate(task.language_bias_condition)
    )
    domain = _numeric_domain_values(task)
    all_positive = bool(domain) and all(value > 0 for value in domain)
    if domain and 0 not in domain and not all_positive:
        parts.append("zero_not_in_numeric_domain.")
    if domain and all(value >= 0 for value in domain) and not all_positive:
        parts.append("numeric_domain_nonnegative.")
    if all_positive:
        parts.append("numeric_domain_positive.")
    parts.extend(
        _closed_world_property_facts(
            properties,
            {
                predicate: identifier
                for predicate, identifier in predicate_ids.items()
                if predicate not in structured_predicates
            },
        )
    )
    for predicate, predicate_id in predicate_ids.items():
        parts.append(
            f"predicate_symbol({predicate_id},{clingo.String(predicate[0])},{predicate[1]})."
        )
        complement = (f"-{predicate[0]}", predicate[1])
        complement_id = predicate_ids.get(complement)
        if not predicate[0].startswith("-") and complement_id is not None:
            parts.append(f"strong_complement_pred({predicate_id},{complement_id}).")
    for layer, predicate in enumerate(task.invented_predicates):
        parts.append(f"invented_pred({predicate_ids[predicate]},{layer}).")
    shapes: dict[tuple[object, ...], int] = {}
    condition_variants: dict[tuple[object, ...], int] = {}
    for mode in modes:
        section_id = mode.section
        predicate_id = mode.id
        if isinstance(mode.literal, AtomLiteral):
            predicate_id = predicate_ids[mode.literal.atom.signature]
        elif isinstance(mode.literal, ConditionalLiteral):
            predicate_id = predicate_ids[mode.literal.conclusion.atom.signature]
        recall = (
            (max_head_literals if mode.section == "head" else max_body_literals)
            if mode.recall < 0
            else mode.recall
        )
        parts.append(
            f"mode({section_id},{mode.id},{predicate_id},{mode.arity},{recall})."
        )
        parts.append(f"recall_group({mode.id},{mode.recall_group}).")
        shape = tuple(argument.shape() for argument in mode.literal.arguments)
        parts.append(f"mode_shape({mode.id},{shapes.setdefault(shape, len(shapes))}).")
        if mode.head_form is not None:
            parts.append(
                f"head_form_member({mode.head_form},{mode.head_position},{mode.id})."
            )
            if mode.aggregate_head:
                parts.append(f"aggregate_head_form({mode.head_form}).")
        for index, binding in zip(_binding_positions(mode), mode.bindings, strict=True):
            parts.append(f"mode_variable_arg({mode.id},{index}).")
            if binding.type != "any":
                parts.append(f"mode_arg_type({mode.id},{index},{binding.type}).")
            if mode.head_form is not None and binding.label:
                parts.append(
                    f"head_arg_label({mode.head_form},{mode.id},{index},{binding.label})."
                )
            if binding.label:
                parts.append(f"mode_arg_label({mode.id},{index},{binding.label}).")
            if binding.direction:
                parts.append(
                    f"mode_arg_direction({mode.id},{index},{binding.direction})."
                )
        if isinstance(mode.literal, AtomLiteral) and mode.literal.default_negated:
            parts.append(f"negative_mode({mode.id}).")
        if isinstance(mode.literal, ConditionalLiteral):
            conditional = mode.literal
            conclusion = conditional.conclusion
            parts.append(
                f"conditional_mode({mode.id},{predicate_ids[conclusion.atom.signature]},{len(conclusion.atom.terms)})."
            )
            if conclusion.default_negated:
                parts.append(f"negative_mode({mode.id}).")
            offset = 0
            conclusion_bindings = len(conclusion.atom.bindings())
            for argument in range(conclusion_bindings):
                parts.append(f"conditional_main_arg({mode.id},{argument}).")
            offset += conclusion_bindings
            for index, condition in enumerate(conditional.conditions):
                if isinstance(condition, AtomLiteral):
                    polarity = "negative" if condition.default_negated else "positive"
                    condition_key = (
                        condition.default_negated,
                        condition.atom.signature,
                        *(term.shape() for term in condition.atom.terms),
                    )
                    parts.append(
                        f"conditional_condition({mode.id},{index},{predicate_ids[condition.atom.signature]},{polarity})."
                    )
                else:
                    condition_key = (
                        condition.operator,
                        *(term.shape() for term in condition.terms),
                    )
                    parts.append(
                        f"conditional_expression_condition({mode.id},{index})."
                    )
                parts.append(
                    f"conditional_condition_variant({mode.id},{index},{condition_variants.setdefault(condition_key, len(condition_variants))})."
                )
                binding_count = sum(
                    len(term.bindings()) for term in condition.arguments
                )
                for relative, argument in enumerate(
                    range(offset, offset + binding_count)
                ):
                    parts.append(
                        f"conditional_condition_arg({mode.id},{index},{relative},{argument})."
                    )
                offset += binding_count
            for group, count in Counter(conditional.condition_groups).items():
                parts.append(f"mode_condition_usage({mode.id},{group},{count}).")
            parts.append(
                f"mode_condition_count({mode.id},{len(conditional.conditions)})."
            )
        if isinstance(mode.literal, ComparisonLiteral):
            parts.append(f"generic_comparison_mode({mode.id}).")
            if mode.literal.operator == "=" and any(
                binding.direction == "output" for binding in mode.bindings
            ):
                parts.append(f"exact_assignment_mode({mode.id}).")
            if not mode.literal.simple:
                pass
            elif mode.literal.operator == "=":
                parts.append(f"eq_comparison_mode({mode.id}).")
            elif mode.literal.operator == "!=":
                parts.append(f"neq_comparison_mode({mode.id}).")
            elif mode.literal.operator == "<":
                parts.append(f"less_than_comparison_mode({mode.id}).")
            elif mode.literal.operator == ">":
                parts.append(f"greater_than_comparison_mode({mode.id}).")
            elif mode.literal.operator == "<=":
                parts.append(f"leq_comparison_mode({mode.id}).")
            elif mode.literal.operator == ">=":
                parts.append(f"geq_comparison_mode({mode.id}).")
        elif isinstance(mode.literal, ArithmeticLiteral):
            arithmetic = mode.literal
            if arithmetic.operator == "+":
                parts.append(f"add_mode({mode.id}).")
            elif arithmetic.operator == "*":
                parts.append(f"mul_mode({mode.id}).")
            elif arithmetic.operator == "/":
                parts.append(f"div_mode({mode.id}).")
            elif arithmetic.operator == "\\":
                parts.append(f"mod_mode({mode.id}).")
            elif arithmetic.operator == "abs":
                parts.append(f"abs_mode({mode.id}).")
        elif isinstance(mode.literal, AggregateLiteral):
            aggregate = mode.literal
            parts.append(
                f"aggregate_mode({mode.id},{len(aggregate.tuple_terms)},{len(aggregate.conditions)})."
            )
            if mode.id in aggregate_has_shorter_mode:
                parts.append(f"aggregate_has_shorter_mode({mode.id}).")
            if aggregate.function == "count":
                parts.append(f"count_aggregate_mode({mode.id}).")
            elif aggregate.function == "sum":
                parts.append(f"sum_aggregate_mode({mode.id}).")
            offset = 0
            for atom_index, atom in enumerate(aggregate.conditions):
                arity = len(atom.terms)
                parts.append(
                    f"aggregate_condition_atom({mode.id},{atom_index},{predicate_ids[atom.signature]},{offset},{arity})."
                )
                offset += arity
    return "\n".join(parts)


def _predicate_ids(modes: list[ClauseMode]) -> dict[Predicate, int]:
    predicate_ids: dict[Predicate, int] = {}
    for mode in modes:
        if isinstance(mode.literal, AtomLiteral):
            predicate_ids.setdefault(mode.literal.atom.signature, len(predicate_ids))
        elif isinstance(mode.literal, ConditionalLiteral):
            predicate_ids.setdefault(
                mode.literal.conclusion.atom.signature, len(predicate_ids)
            )
            for condition in mode.literal.conditions:
                if isinstance(condition, AtomLiteral):
                    predicate_ids.setdefault(
                        condition.atom.signature, len(predicate_ids)
                    )
        elif isinstance(mode.literal, AggregateLiteral):
            for atom in mode.literal.conditions:
                predicate_ids.setdefault(atom.signature, len(predicate_ids))
    return predicate_ids


def _closed_world_property_facts(
    properties: ClosedWorldProperties,
    predicate_ids: dict[Predicate, int],
) -> list[str]:
    parts: list[str] = []

    def pred_id(predicate: Predicate) -> int | None:
        return predicate_ids.get(predicate)

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
        for target_arg, source_arg in enumerate(projection):
            parts.append(f"project_arg({projection_id},{target_arg},{source_arg}).")
        projection_id += 1
    for left, left_arg, right, right_arg in sorted(properties.disjoint_projection):
        left_id = pred_id(left)
        right_id = pred_id(right)
        if left_id is not None and right_id is not None:
            parts.append(f"disjoint_arg({left_id},{left_arg},{right_id},{right_arg}).")
    tuple_mutex_id = 0
    for left, right, projection in sorted(properties.tuple_mutex):
        left_id = pred_id(left)
        right_id = pred_id(right)
        if left_id is None or right_id is None:
            continue
        parts.append(f"tuple_mutex_pred({left_id},{right_id},{tuple_mutex_id}).")
        for right_arg, left_arg in enumerate(projection):
            parts.append(f"tuple_mutex_arg({tuple_mutex_id},{right_arg},{left_arg}).")
        tuple_mutex_id += 1
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
    partition_id = 0
    for group in sorted(properties.partitions):
        ids = [pred_id(predicate) for predicate in group]
        if any(identifier is None for identifier in ids):
            continue
        for identifier in ids:
            parts.append(f"partition_pred({partition_id},{identifier}).")
        partition_id += 1
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
        for input_arg in input_args:
            parts.append(f"functional_set_arg({fd_id},{input_arg}).")
        fd_id += 1
    key_id = 0
    for predicate, args in sorted(properties.keys):
        if (identifier := pred_id(predicate)) is None:
            continue
        parts.append(f"key_pred({identifier},{key_id}).")
        for arg in args:
            parts.append(f"key_arg({key_id},{arg}).")
        key_id += 1
    for predicate, upper in sorted(properties.cardinality_upper):
        if (identifier := pred_id(predicate)) is not None:
            parts.append(f"cardinality_upper_pred({identifier},{upper}).")
    for predicate in sorted(properties.transitive):
        if (identifier := pred_id(predicate)) is not None:
            parts.append(f"transitive_pred({identifier}).")
    return parts
