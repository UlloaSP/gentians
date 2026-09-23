from collections import Counter

from ..language.asp import Predicate
from ..language.ir.aggregate_literal import AggregateLiteral
from ..language.ir.arithmetic_literal import ArithmeticLiteral
from ..language.ir.atom_literal import AtomLiteral
from ..language.ir.comparison_literal import ComparisonLiteral
from ..language.ir.conditional_literal import ConditionalLiteral
from ..language.ir.head_aggregate_element import HeadAggregateElement
from .clause_mode import ClauseMode


def predicate_ids(modes: list[ClauseMode]) -> dict[Predicate, int]:
    identifiers: dict[Predicate, int] = {}
    for mode in modes:
        if isinstance(mode.literal, AtomLiteral):
            identifiers.setdefault(mode.literal.atom.signature, len(identifiers))
        elif isinstance(mode.literal, ConditionalLiteral):
            identifiers.setdefault(
                mode.literal.conclusion.atom.signature, len(identifiers)
            )
            for condition in mode.literal.conditions:
                if isinstance(condition, AtomLiteral):
                    identifiers.setdefault(condition.atom.signature, len(identifiers))
        elif isinstance(mode.literal, AggregateLiteral):
            for element in mode.literal.elements:
                for atom in element.conditions:
                    identifiers.setdefault(atom.signature, len(identifiers))
        elif isinstance(mode.literal, HeadAggregateElement):
            identifiers.setdefault(mode.literal.atom.signature, len(identifiers))
            for atom in mode.literal.conditions:
                identifiers.setdefault(atom.signature, len(identifiers))
    return identifiers


def compile_mode_facts(
    modes: list[ClauseMode],
    predicate_ids: dict[Predicate, int],
    max_head_literals: int,
    max_body_literals: int,
) -> list[str]:
    shapes: dict[tuple[object, ...], int] = {}
    condition_variants: dict[tuple[object, ...], int] = {}
    aggregates = tuple(
        literal
        for mode in modes
        if isinstance((literal := mode.literal), AggregateLiteral)
    )
    parts: list[str] = []
    for mode in modes:
        parts.extend(
            _common_mode_facts(
                mode,
                predicate_ids,
                shapes,
                max_head_literals,
                max_body_literals,
            )
        )
        if isinstance(mode.literal, ConditionalLiteral):
            parts.extend(
                _conditional_facts(
                    mode, mode.literal, predicate_ids, condition_variants
                )
            )
        elif isinstance(mode.literal, ComparisonLiteral):
            parts.extend(_comparison_facts(mode, mode.literal))
        elif isinstance(mode.literal, ArithmeticLiteral):
            parts.extend(_arithmetic_facts(mode, mode.literal))
        elif isinstance(mode.literal, AggregateLiteral):
            parts.extend(_aggregate_facts(mode, mode.literal, aggregates, predicate_ids))
        elif isinstance(mode.literal, HeadAggregateElement):
            parts.extend(_head_aggregate_facts(mode, mode.literal, predicate_ids))
    return parts


def _common_mode_facts(
    mode: ClauseMode,
    predicate_ids: dict[Predicate, int],
    shapes: dict[tuple[object, ...], int],
    max_head_literals: int,
    max_body_literals: int,
) -> list[str]:
    recall = (
        max_head_literals if mode.section == "head" else max_body_literals
    ) if mode.recall < 0 else mode.recall
    parts = [
        f"mode_section({mode.id},{mode.section}).",
        f"mode_recall({mode.id},{recall}).",
        f"mode_kind({mode.id},{mode.literal.kind}).",
    ]
    atom = None
    if isinstance(mode.literal, AtomLiteral):
        atom = mode.literal.atom
    elif isinstance(mode.literal, ConditionalLiteral):
        atom = mode.literal.conclusion.atom
    elif isinstance(mode.literal, HeadAggregateElement):
        atom = mode.literal.atom
    if atom is not None:
        parts.append(
            f"mode_atom({mode.id},{predicate_ids[atom.signature]},{len(atom.terms)})."
        )
    parts.append(f"recall_group({mode.id},{mode.recall_group}).")
    shape: tuple[object, ...] = tuple(
        argument.shape() for argument in mode.literal.arguments
    )
    if isinstance(mode.literal, ComparisonLiteral):
        shape = (
            "comparison",
            mode.literal.default_negated,
            mode.literal.operators,
            shape,
        )
    elif isinstance(mode.literal, ArithmeticLiteral):
        shape = ("arithmetic", mode.literal.operator, shape)
    elif isinstance(mode.literal, AggregateLiteral):
        shape = (
            "aggregate",
            mode.literal.function,
            tuple(
                (len(element.terms), len(element.conditions))
                for element in mode.literal.elements
            ),
            mode.literal.left_guard.operator if mode.literal.left_guard else None,
            mode.literal.right_guard.operator if mode.literal.right_guard else None,
            shape,
        )
    parts.append(f"mode_shape({mode.id},{shapes.setdefault(shape, len(shapes))}).")
    if mode.head_form is not None:
        parts.append(f"head_form_member({mode.head_form},{mode.head_position},{mode.id}).")
        if mode.head is not None and mode.head.kind in {"choice", "aggregate"}:
            parts.append(f"composite_head_form({mode.head_form}).")
        if (
            mode.head is not None
            and mode.head.kind in {"normal", "disjunction"}
            and isinstance(mode.literal, AtomLiteral)
        ):
            parts.append(f"plain_disjunctive_head_mode({mode.id}).")
    for index, binding in zip(mode.binding_positions, mode.bindings, strict=True):
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
            parts.append(f"mode_arg_direction({mode.id},{index},{binding.direction}).")
    if isinstance(mode.literal, AtomLiteral) and mode.literal.default_negated:
        parts.append(f"negative_mode({mode.id}).")
    return parts


def _conditional_facts(
    mode: ClauseMode,
    conditional: ConditionalLiteral,
    predicate_ids: dict[Predicate, int],
    condition_variants: dict[tuple[object, ...], int],
) -> list[str]:
    parts: list[str] = []
    if conditional.conclusion.default_negated:
        parts.append(f"negative_mode({mode.id}).")
    offset = len(conditional.conclusion.atom.bindings())
    parts.extend(f"conditional_main_arg({mode.id},{arg})." for arg in range(offset))
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
                condition.default_negated,
                condition.operators,
                *(term.shape() for term in condition.terms),
            )
        parts.append(
            f"conditional_condition_variant({mode.id},{index},{condition_variants.setdefault(condition_key, len(condition_variants))})."
        )
        binding_count = sum(len(term.bindings()) for term in condition.arguments)
        parts.extend(
            f"conditional_condition_arg({mode.id},{index},{relative},{argument})."
            for relative, argument in enumerate(range(offset, offset + binding_count))
        )
        offset += binding_count
    parts.extend(
        f"mode_condition_usage({mode.id},{group},{count})."
        for group, count in Counter(conditional.condition_groups).items()
    )
    parts.append(f"mode_condition_count({mode.id},{len(conditional.conditions)}).")
    return parts


def _comparison_facts(
    mode: ClauseMode, comparison: ComparisonLiteral
) -> list[str]:
    parts: list[str] = []
    if any(binding.direction == "output" for binding in mode.bindings):
        parts.append(f"relation_output_mode({mode.id}).")
    operator = comparison.operators[0] if len(comparison.operators) == 1 else None
    operator_name = (
        {
            "=": "eq",
            "!=": "neq",
            "<": "lt",
            ">": "gt",
            "<=": "leq",
            ">=": "geq",
        }.get(operator)
        if comparison.simple
        else None
    )
    if operator_name is not None:
        parts.append(f"comparison_operator({mode.id},{operator_name}).")
    offsets: list[int] = []
    offset = 0
    for term in comparison.terms:
        offsets.append(offset)
        offset += len(term.bindings())
    for index, operator in enumerate(comparison.operators):
        if (
            operator in {"<", ">"}
            and comparison.terms[index].kind == "variable"
            and comparison.terms[index + 1].kind == "variable"
        ):
            parts.append(
                f"strict_comparison_args({mode.id},{offsets[index]},{offsets[index + 1]})."
            )
    return parts


def _arithmetic_facts(
    mode: ClauseMode, arithmetic: ArithmeticLiteral
) -> list[str]:
    positions: list[tuple[int, ...]] = []
    offset = 0
    for term in arithmetic.arguments:
        bindings = term.bindings()
        positions.append(tuple(range(offset, offset + len(bindings))))
        offset += len(bindings)
    complete = all(len(term_positions) == 1 for term_positions in positions)
    if not complete:
        return []
    left, right, result = (term_positions[0] for term_positions in positions)
    parts = [
        f"mode_arithmetic_operand({mode.id},left,{left}).",
        f"mode_arithmetic_operand({mode.id},right,{right}).",
        f"mode_arithmetic_result({mode.id},{result}).",
    ]
    relation = None
    if arithmetic.operator == "+" and _operands_are_interchangeable(arithmetic):
        relation = "add_mode"
    elif arithmetic.operator == "*" and _operands_are_interchangeable(arithmetic):
        relation = "mul_mode"
    elif arithmetic.operator == "/":
        relation = "div_mode"
    elif arithmetic.operator == "\\":
        relation = "mod_mode"
    elif arithmetic.operator == "abs" and _operands_are_interchangeable(arithmetic):
        relation = "abs_mode"
    if relation is not None:
        parts.append(f"{relation}({mode.id}).")
    return parts


def _aggregate_facts(
    mode: ClauseMode,
    aggregate: AggregateLiteral,
    aggregates: tuple[AggregateLiteral, ...],
    predicate_ids: dict[Predicate, int],
) -> list[str]:
    parts: list[str] = []
    offset = 0
    for element_id, element in enumerate(aggregate.elements):
        for tuple_position, term in enumerate(element.terms):
            for position in range(offset, offset + len(term.bindings())):
                parts.append(
                    f"mode_aggregate_element_tuple_arg({mode.id},{element_id},{tuple_position},{position})."
                )
            offset += len(term.bindings())
        for condition, atom in enumerate(element.conditions):
            parts.append(
                f"aggregate_element_condition_atom({mode.id},{element_id},{condition},{predicate_ids[atom.signature]},{len(atom.terms)})."
            )
            for argument, term in enumerate(atom.terms):
                for position in range(offset, offset + len(term.bindings())):
                    parts.append(
                        f"mode_aggregate_element_condition_arg({mode.id},{element_id},{condition},{argument},{position})."
                    )
                offset += len(term.bindings())
    for guard in (aggregate.left_guard, aggregate.right_guard):
        if guard is None:
            continue
        name = "mode_aggregate_output_arg" if guard is aggregate.output_guard else "mode_aggregate_guard_arg"
        for position in range(offset, offset + len(guard.term.bindings())):
            parts.append(f"{name}({mode.id},{position}).")
        offset += len(guard.term.bindings())

    if len(aggregate.elements) != 1 or aggregate.output_guard is None:
        return parts
    element = aggregate.elements[0]
    tuple_arity = len(element.terms)
    parts.append(f"aggregate_shape({mode.id},{tuple_arity},{len(element.conditions)}).")
    if any(
        other.function == aggregate.function
        and len(other.elements) == 1
        and other.output_guard is not None
        and other.elements[0].conditions == element.conditions
        and len(other.elements[0].terms) == tuple_arity - 1
        for other in aggregates
    ):
        parts.append(f"aggregate_has_shorter_mode({mode.id}).")
    if aggregate.function == "count":
        parts.append(f"count_aggregate_mode({mode.id}).")
    elif aggregate.function == "sum":
        parts.append(f"sum_aggregate_mode({mode.id}).")
    offset = 0
    for tuple_position, term in enumerate(element.terms):
        binding_count = len(term.bindings())
        parts.extend(
            f"mode_aggregate_tuple_arg({mode.id},{tuple_position},{flat_position})."
            for flat_position in range(offset, offset + binding_count)
        )
        offset += binding_count
    for condition, atom in enumerate(element.conditions):
        arity = len(atom.terms)
        parts.append(
            f"aggregate_condition_atom({mode.id},{condition},{predicate_ids[atom.signature]},{arity})."
        )
        for argument, term in enumerate(atom.terms):
            binding_count = len(term.bindings())
            parts.extend(
                f"mode_aggregate_condition_arg({mode.id},{condition},{argument},{flat_position})."
                for flat_position in range(offset, offset + binding_count)
            )
            offset += binding_count
    result_bindings = aggregate.output_guard.term.bindings()
    parts.extend(
        f"mode_aggregate_result_arg({mode.id},{position})."
        for position in range(offset, offset + len(result_bindings))
    )
    return parts


def _head_aggregate_facts(
    mode: ClauseMode,
    element: HeadAggregateElement,
    predicate_ids: dict[Predicate, int],
) -> list[str]:
    parts: list[str] = []
    offset = 0
    for term in (*element.terms, *element.atom.terms):
        for position in range(offset, offset + len(term.bindings())):
            parts.append(f"head_aggregate_element_arg({mode.id},{position}).")
        offset += len(term.bindings())
    for condition, atom in enumerate(element.conditions):
        parts.append(
            f"head_aggregate_condition_atom({mode.id},{condition},{predicate_ids[atom.signature]})."
        )
        for term in atom.terms:
            for position in range(offset, offset + len(term.bindings())):
                parts.append(f"head_aggregate_condition_arg({mode.id},{condition},{position}).")
                parts.append(f"head_aggregate_element_arg({mode.id},{position}).")
            offset += len(term.bindings())
    parts.append(f"mode_condition_count({mode.id},{len(element.conditions)}).")
    return parts


def _operands_are_interchangeable(literal: ArithmeticLiteral) -> bool:
    left, right = literal.expression.arguments
    left_bindings = left.bindings()
    right_bindings = right.bindings()
    if len(left_bindings) != 1 or len(right_bindings) != 1:
        return False
    left_binding = left_bindings[0]
    right_binding = right_bindings[0]
    return (
        left_binding.type,
        left_binding.direction,
        left_binding.label,
    ) == (
        right_binding.type,
        right_binding.direction,
        right_binding.label,
    )
