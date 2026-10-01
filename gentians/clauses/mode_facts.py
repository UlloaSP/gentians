from collections import Counter
from itertools import combinations, product

from clingo import ast

from ..language import terms as mode_terms
from ..language.asp import Predicate
from ..language.ast_nodes import COMPARISON_OPERATORS
from ..language.ir.aggregate_literal import AggregateLiteral
from .arithmetic_literal import ArithmeticLiteral
from ..language.ir.atom_literal import AtomLiteral
from ..language.ir.atom_template import AtomTemplate
from ..language.ir.boolean_literal import BooleanLiteral
from ..language.ir.comparison_literal import ComparisonLiteral
from ..language.ir.conditional_literal import ConditionalLiteral
from ..language.ir.head_aggregate_element import HeadAggregateElement
from ..language.modes import _comparison_outputs_are_safe, _with_binding_directions
from .clause_mode import ClauseMode

_COMPARISON_SYMBOLS = {value: key for key, value in COMPARISON_OPERATORS.items()}

def predicate_ids(modes: list[ClauseMode]) -> dict[Predicate, int]:
    identifiers: dict[Predicate, int] = {}
    for mode in modes:
        if isinstance(mode.literal, AtomLiteral):
            identifiers.setdefault(mode.literal.atom.signature, len(identifiers))
        elif isinstance(mode.literal, ConditionalLiteral):
            if isinstance(mode.literal.conclusion, AtomLiteral):
                identifiers.setdefault(
                    mode.literal.conclusion.atom.signature, len(identifiers)
                )
            for condition in mode.literal.conditions:
                if isinstance(condition, AtomLiteral):
                    identifiers.setdefault(condition.atom.signature, len(identifiers))
        elif isinstance(mode.literal, AggregateLiteral):
            for element in mode.literal.elements:
                if isinstance(element.conclusion, AtomLiteral):
                    identifiers.setdefault(element.conclusion.atom.signature, len(identifiers))
                for condition in element.conditions:
                    if isinstance(condition, AtomLiteral):
                        identifiers.setdefault(
                            condition.atom.signature, len(identifiers)
                        )
        elif isinstance(mode.literal, HeadAggregateElement):
            if isinstance(mode.literal.conclusion, AtomLiteral):
                identifiers.setdefault(mode.literal.conclusion.atom.signature, len(identifiers))
            for condition in mode.literal.conditions:
                if isinstance(condition, AtomLiteral):
                    identifiers.setdefault(
                        condition.atom.signature, len(identifiers)
                    )
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
        (literal, mode.output_guard)
        for mode in modes
        if isinstance((literal := mode.literal), AggregateLiteral)
    )
    conditional_forms = {
        _conditional_form(mode.section, literal.conclusion, literal.conditions)
        for mode in modes
        if isinstance((literal := mode.literal), ConditionalLiteral)
    }
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
            conditions = mode.literal.conditions
            parts.extend(
                f"conditional_shorter_mode({mode.id},{index})."
                for index in range(len(conditions))
                if _conditional_form(
                    mode.section,
                    mode.literal.conclusion,
                    conditions[:index] + conditions[index + 1 :],
                )
                in conditional_forms
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


def _conditional_form(
    section: str, conclusion: object, conditions: tuple[object, ...]
) -> tuple[object, ...]:
    """A conditional template up to the order of its conditions."""
    return section, conclusion, tuple(sorted(conditions, key=repr))


def _effective_recall(mode: ClauseMode, max_head_literals: int, max_body_literals: int) -> int:
    """Recall with an unlimited source recall replaced by its section capacity."""
    if mode.recall >= 0:
        return mode.recall
    return max_head_literals if mode.section == "head" else max_body_literals


def _plain_disjunctive_head(mode: ClauseMode) -> bool:
    return (
        mode.head is not None
        and mode.head.kind in {"normal", "disjunction"}
        and isinstance(mode.literal, AtomLiteral)
        and not mode.literal.default_negated
    )


# Enumerated theta substitutions ground roughly combinations x slots^2 x vars^2
# rules. Beyond this many offset combinations the saturation encoding is used.
THETA_OFFSET_LIMIT = 1024


def theta_facts(
    modes: list[ClauseMode], max_head_literals: int, max_body_literals: int
) -> list[str]:
    """Select and parameterize the theta-reduction encoding of theta.lp.

    Only normal body atoms move. A repeated one maps to Start + Offset inside
    its contiguous mode group; offsets range below the largest group the body
    can hold, and every combination over the body slots becomes a theta_sigma.
    """
    group = max(
        (
            min(_effective_recall(mode, max_head_literals, max_body_literals), max_body_literals)
            for mode in modes
            if mode.section == "body" and isinstance(mode.literal, AtomLiteral)
        ),
        default=1,
    )
    if group < 2:
        return []
    if group ** max_body_literals > THETA_OFFSET_LIMIT:
        return ["theta_saturated_section(body)."]
    parts = ["theta_sigma_section(body)."]
    for identifier, offsets in enumerate(product(range(group), repeat=max_body_literals)):
        parts.append(f"theta_sigma({identifier}).")
        parts.extend(
            f"theta_sigma_offset({identifier},body,{slot},{offset})."
            for slot, offset in enumerate(offsets)
        )
    return parts


def _common_mode_facts(
    mode: ClauseMode,
    predicate_ids: dict[Predicate, int],
    shapes: dict[tuple[object, ...], int],
    max_head_literals: int,
    max_body_literals: int,
) -> list[str]:
    recall = _effective_recall(mode, max_head_literals, max_body_literals)
    parts = [
        f"mode_section({mode.id},{mode.section}).",
        f"mode_recall({mode.id},{recall}).",
        f"mode_kind({mode.id},{mode.literal.kind}).",
    ]
    atom = None
    if isinstance(mode.literal, AtomLiteral):
        atom = mode.literal.atom
    elif isinstance(mode.literal, ConditionalLiteral):
        if isinstance(mode.literal.conclusion, AtomLiteral):
            atom = mode.literal.conclusion.atom
    elif isinstance(mode.literal, HeadAggregateElement) and isinstance(mode.literal.conclusion, AtomLiteral):
        atom = mode.literal.conclusion.atom
    if atom is not None:
        parts.append(
            f"mode_atom({mode.id},{predicate_ids[atom.signature]},{len(atom.terms)})."
        )
    parts.append(f"recall_group({mode.id},{mode.recall_group}).")
    shape: tuple[object, ...] = tuple(
        mode_terms.shape(argument) for argument in mode.arguments
    )
    if isinstance(mode.literal, ComparisonLiteral):
        shape = (
            "comparison",
            mode.literal.default_negated,
            mode.literal.double_negated,
            mode.literal.operators,
            shape,
        )
    elif isinstance(mode.literal, ArithmeticLiteral):
        shape = ("arithmetic", mode.literal.operator, shape)
    elif isinstance(mode.literal, AtomLiteral) and mode.literal.atom.alternatives:
        shape = (
            "pooled_atom",
            tuple(
                tuple(mode_terms.shape(term) for term in alternative)
                for alternative in mode.literal.atom.alternatives
            ),
        )
    elif isinstance(mode.literal, BooleanLiteral):
        shape = ("boolean", mode.literal.value, mode.literal.default_negated, mode.literal.double_negated)
    elif isinstance(mode.literal, AggregateLiteral):
        shape = (
            "aggregate",
            mode.literal.function,
            mode.literal.default_negated,
            mode.literal.double_negated,
            tuple(
                (len(element.terms), len(element.conditions),
                 _aggregate_conclusion_shape(element.conclusion))
                for element in mode.literal.elements
            ),
            _COMPARISON_SYMBOLS[mode.literal.left_guard.comparison] if mode.literal.left_guard else None,
            _COMPARISON_SYMBOLS[mode.literal.right_guard.comparison] if mode.literal.right_guard else None,
            shape,
        )
    parts.append(f"mode_shape({mode.id},{shapes.setdefault(shape, len(shapes))}).")
    if mode.section == "body" and isinstance(mode.literal, AtomLiteral):
        alternatives = _pool_alternative_positions(mode.literal.atom)
        if _binds_partially(alternatives, mode.literal.atom):
            for alternative, positions in enumerate(alternatives):
                parts.append(f"mode_pool_alternative({mode.id},{alternative}).")
                parts.extend(
                    f"mode_pool_alternative_arg({mode.id},{alternative},{position})."
                    for position in sorted(positions)
                )
    if isinstance(mode.literal, AtomLiteral) and _atom_arguments_are_interchangeable(
        mode.literal.atom
    ):
        parts.append(f"interchangeable_operands({mode.id}).")
    if mode.head_form is not None:
        parts.append(f"head_form_member({mode.head_form},{mode.head_position},{mode.id}).")
        if mode.head is not None and mode.head.kind in {"choice", "aggregate"}:
            parts.append(f"composite_head_form({mode.head_form}).")
        if _plain_disjunctive_head(mode):
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
    guard_start = mode.literal_binding_count
    parts.extend(
        f"head_guard_arg({mode.id},{position})."
        for position in range(guard_start, len(mode.bindings))
    )
    if isinstance(mode.literal, AtomLiteral | ComparisonLiteral) and mode.literal.default_negated:
        parts.append(f"negative_mode({mode.id}).")
        if mode.literal.double_negated:
            parts.append(f"double_negative_mode({mode.id}).")
    if isinstance(mode.literal, AggregateLiteral) and mode.literal.default_negated:
        parts.append(f"negative_mode({mode.id}).")
        if mode.literal.double_negated:
            parts.append(f"double_negative_mode({mode.id}).")
    if isinstance(mode.literal, ConditionalLiteral) and mode.literal.conclusion.default_negated:
        parts.append(f"negative_mode({mode.id}).")
        if mode.literal.conclusion.double_negated:
            parts.append(f"double_negative_mode({mode.id}).")
    if isinstance(mode.literal, HeadAggregateElement) and mode.literal.conclusion.default_negated:
        parts.append(f"negative_mode({mode.id}).")
        if mode.literal.conclusion.double_negated:
            parts.append(f"double_negative_mode({mode.id}).")
    return parts


def _pool_alternative_positions(atom: AtomTemplate) -> tuple[frozenset[int], ...]:
    groups = atom.alternatives or (atom.terms,)
    offset = 0
    alternatives: list[frozenset[int]] = []
    for terms in groups:
        term_alternatives = []
        for term in terms:
            term_alternatives.append(_term_alternative_positions(term, offset))
            offset += len(mode_terms.bindings(term))
        alternatives.extend(
            frozenset().union(*choice)
            for choice in product(*term_alternatives)
        )
    return tuple(alternatives)


def _aggregate_conclusion_shape(
    conclusion: AtomLiteral | BooleanLiteral | ComparisonLiteral | None,
) -> tuple[object, ...] | None:
    if isinstance(conclusion, AtomLiteral):
        return ("atom", conclusion.atom.signature,
                conclusion.default_negated, conclusion.double_negated)
    if isinstance(conclusion, BooleanLiteral):
        return ("boolean", conclusion.value,
                conclusion.default_negated, conclusion.double_negated)
    if isinstance(conclusion, ComparisonLiteral):
        return ("comparison", conclusion.operators,
                conclusion.default_negated, conclusion.double_negated)
    return None


def _binds_partially(
    alternatives: tuple[frozenset[int], ...], atom: AtomTemplate
) -> bool:
    """Whether some placeholder of a positive atom does not ground its variable."""
    return len(alternatives) > 1 or alternatives[0] != frozenset(
        range(len(atom.bindings()))
    )


# Clingo grounds a variable inside arithmetic only by inverting a linear term
# with that single occurrence: q(X+1), q(2*X-1) and q(-X) bind X, while
# q(X+Y), q(X+X), q(|X|), q(X/2), q(X\2) and q(X..3) do not.
_INVERTIBLE_OPERATORS = frozenset({"+", "-", "*", "neg"})


def _is_linear(term: ast.AST) -> bool:
    pending = [term]
    while pending:
        node = pending.pop()
        if mode_terms.kind(node) == "arithmetic":
            if mode_terms.value(node) not in _INVERTIBLE_OPERATORS:
                return False
            pending.extend(mode_terms.arguments(node))
        elif mode_terms.kind(node) not in {"variable", "constant", "fixed"}:
            return False
    return True


def _term_alternative_positions(
    term: ast.AST, offset: int
) -> tuple[frozenset[int], ...]:
    """Placeholder positions each pool alternative grounds, per Clingo safety."""
    pending = [(term, offset, False)]
    result: list[tuple[frozenset[int], ...]] = []
    while pending:
        node, node_offset, visited = pending.pop()
        node_kind = mode_terms.kind(node)
        if node_kind == "variable":
            result.append((frozenset((node_offset,)),))
        elif node_kind in {"arithmetic", "interval"}:
            binds = len(mode_terms.bindings(node)) == 1 and _is_linear(node)
            result.append((frozenset((node_offset,)) if binds else frozenset(),))
        elif visited:
            count = len(mode_terms.arguments(node))
            alternatives = result[-count:] if count else []
            if count:
                del result[-count:]
            result.append(
                tuple(choice for group in alternatives for choice in group)
                if node_kind == "pool" else tuple(
                    frozenset().union(*choice) for choice in product(*alternatives)
                )
            )
        else:
            pending.append((node, node_offset, True))
            children = []
            for child in mode_terms.arguments(node):
                children.append((child, node_offset, False))
                node_offset += len(mode_terms.bindings(child))
            pending.extend(reversed(children))
    return result[0]


def _conditional_facts(
    mode: ClauseMode,
    conditional: ConditionalLiteral,
    predicate_ids: dict[Predicate, int],
    condition_variants: dict[tuple[object, ...], int],
) -> list[str]:
    parts: list[str] = []
    argument_index = len(conditional.conclusion.arguments)
    offset = mode.argument_offsets[argument_index]
    parts.extend(f"conditional_main_arg({mode.id},{arg})." for arg in range(offset))
    for index, condition in enumerate(conditional.conditions):
        if isinstance(condition, AtomLiteral):
            polarity = "negative" if condition.default_negated else "positive"
            if not condition.default_negated:
                parts.extend(_local_pool_facts(
                    mode.id, "conditional", -1, index, offset, condition.atom,
                ))
            condition_key = (
                condition.default_negated,
                condition.double_negated,
                condition.atom.signature,
                *(mode_terms.shape(term) for term in condition.atom.binding_terms),
            )
            parts.append(
                f"conditional_condition({mode.id},{index},{predicate_ids[condition.atom.signature]},{polarity})."
            )
        elif isinstance(condition, BooleanLiteral):
            condition_key = (
                "boolean", condition.value, condition.default_negated,
                condition.double_negated,
            )
        else:
            condition_key = (
                condition.default_negated,
                condition.double_negated,
                condition.operators,
                *(mode_terms.shape(term) for term in condition.terms),
            )
        # Conditions are ordered and deduplicated by variant, which amounts to
        # swapping them. Only conditions with equal types, directions and
        # labels can swap.
        argument_index += len(condition.arguments)
        end = mode.argument_offsets[argument_index]
        condition_key = (*condition_key, tuple(
            (binding.type, binding.direction, binding.label)
            for binding in mode.bindings[offset:end]
        ))
        parts.append(
            f"conditional_condition_variant({mode.id},{index},{condition_variants.setdefault(condition_key, len(condition_variants))})."
        )
        binding_count = end - offset
        if isinstance(condition, ComparisonLiteral):
            parts.extend(_local_comparison_facts(
                mode.id, "conditional", -1, index, offset, condition,
            ))
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
        if _terms_are_interchangeable(*comparison.terms):
            parts.append(f"interchangeable_operands({mode.id}).")
    offsets = mode.argument_offsets
    for index, operator in enumerate(comparison.operators):
        if (
            operator in {"<", ">"}
            and mode_terms.kind(comparison.terms[index]) == "variable"
            and mode_terms.kind(comparison.terms[index + 1]) == "variable"
        ):
            parts.append(
                f"strict_comparison_args({mode.id},{offsets[index]},{offsets[index + 1]})."
            )
    return parts


def _arithmetic_facts(
    mode: ClauseMode, arithmetic: ArithmeticLiteral
) -> list[str]:
    positions = [tuple(range(start, end)) for start, end in zip(mode.argument_offsets, mode.argument_offsets[1:])]
    complete = all(len(term_positions) == 1 for term_positions in positions)
    if not complete:
        return []
    left, right, result = (term_positions[0] for term_positions in positions)
    parts = [
        f"mode_arithmetic_operand({mode.id},left,{left}).",
        f"mode_arithmetic_operand({mode.id},right,{right}).",
        f"mode_arithmetic_result({mode.id},{result}).",
    ]
    relation = {
        "+": "add_mode",
        "*": "mul_mode",
        "/": "div_mode",
        "\\": "mod_mode",
        "abs": "abs_mode",
    }.get(arithmetic.operator)
    if relation is not None:
        parts.append(f"{relation}({mode.id}).")
    if _operands_are_interchangeable(arithmetic):
        parts.append(f"interchangeable_operands({mode.id}).")
    return parts


def _aggregate_facts(
    mode: ClauseMode,
    aggregate: AggregateLiteral,
    aggregates: tuple[tuple[AggregateLiteral, ast.AST | None], ...],
    predicate_ids: dict[Predicate, int],
) -> list[str]:
    output_guard = mode.output_guard
    parts: list[str] = []
    offset = 0
    ranges = iter(zip(mode.argument_offsets, mode.argument_offsets[1:]))
    for element_id, element in enumerate(aggregate.elements):
        for tuple_position, term in enumerate(element.terms):
            offset, end = next(ranges)
            for position in range(offset, end):
                parts.append(
                    f"mode_aggregate_element_tuple_arg({mode.id},{element_id},{tuple_position},{position})."
                )
            offset = end
        if element.conclusion is not None:
            if isinstance(element.conclusion, AtomLiteral):
                atom = element.conclusion.atom
                parts.append(
                    f"aggregate_element_atom({mode.id},{element_id},{predicate_ids[atom.signature]},{len(atom.terms)})."
                )
            for argument, term in enumerate(element.conclusion.arguments):
                offset, end = next(ranges)
                for position in range(offset, end):
                    parts.append(
                        f"mode_aggregate_element_tuple_arg({mode.id},{element_id},{argument},{position})."
                    )
                offset = end
        for condition, literal in enumerate(element.conditions):
            if isinstance(literal, AtomLiteral) and not literal.default_negated:
                parts.extend(_local_pool_facts(
                    mode.id, "aggregate", element_id, condition, offset, literal.atom,
                ))
            if isinstance(literal, ComparisonLiteral):
                parts.extend(_local_comparison_facts(
                    mode.id, "aggregate", element_id, condition, offset, literal,
                ))
            if isinstance(literal, AtomLiteral):
                atom = literal.atom
                parts.append(
                    f"aggregate_element_condition_atom({mode.id},{element_id},{condition},{predicate_ids[atom.signature]},{len(atom.terms)})."
                )
            for argument, term in enumerate(literal.arguments):
                offset, end = next(ranges)
                for position in range(offset, end):
                    parts.append(
                        f"mode_aggregate_element_condition_arg({mode.id},{element_id},{condition},{argument},{position})."
                    )
                    if isinstance(literal, AtomLiteral) and not literal.default_negated:
                        parts.append(
                            f"mode_aggregate_element_positive_arg({mode.id},{element_id},{condition},{position})."
                        )
                offset = end
    for guard in (aggregate.left_guard, aggregate.right_guard):
        if guard is None:
            continue
        name = "mode_aggregate_output_arg" if guard is output_guard else "mode_aggregate_guard_arg"
        offset, end = next(ranges)
        for position in range(offset, end):
            parts.append(f"{name}({mode.id},{position}).")
        offset = end

    if (
        len(aggregate.elements) != 1
        or aggregate.function == "set"
        or not aggregate.elements[0].conditions
        or output_guard is None
        or any(
            not isinstance(condition, AtomLiteral) or condition.default_negated
            for condition in aggregate.elements[0].conditions
        )
        or any(
            end - start > 1
            for start, end in zip(mode.argument_offsets, mode.argument_offsets[1:len(aggregate.elements[0].arguments) + 1])
        )
    ):
        return parts
    element = aggregate.elements[0]
    tuple_arity = len(element.terms)
    parts.append(f"aggregate_shape({mode.id},{tuple_arity},{len(element.conditions)}).")
    if any(
        other.function == aggregate.function
        and len(other.elements) == 1
        and other_output_guard is not None
        and other.elements[0].conditions == element.conditions
        and len(other.elements[0].terms) == tuple_arity - 1
        for other, other_output_guard in aggregates
    ):
        parts.append(f"aggregate_has_shorter_mode({mode.id}).")
    if aggregate.function == "count":
        parts.append(f"count_aggregate_mode({mode.id}).")
    elif aggregate.function == "sum":
        parts.append(f"sum_aggregate_mode({mode.id}).")
    offset = 0
    ranges = iter(zip(mode.argument_offsets, mode.argument_offsets[1:]))
    for tuple_position, term in enumerate(element.terms):
        offset, end = next(ranges)
        parts.extend(
            f"mode_aggregate_tuple_arg({mode.id},{tuple_position},{flat_position})."
            for flat_position in range(offset, end)
        )
        offset = end
    parts.extend(
        f"interchangeable_tuple_args({mode.id},{first},{second})."
        for first, second in combinations(range(tuple_arity), 2)
        if _terms_are_interchangeable(element.terms[first], element.terms[second])
    )
    for condition, literal in enumerate(element.conditions):
        assert isinstance(literal, AtomLiteral)
        atom = literal.atom
        arity = len(atom.terms)
        parts.append(
            f"aggregate_condition_atom({mode.id},{condition},{predicate_ids[atom.signature]},{arity})."
        )
        if not atom.alternatives:
            parts.extend(
                f"interchangeable_condition_args({mode.id},{condition},{first},{second})."
                for first, second in combinations(range(arity), 2)
                if all(mode_terms.kind(atom.terms[index]) == "variable" for index in (first, second))
                and _terms_are_interchangeable(atom.terms[first], atom.terms[second])
            )
        for argument, term in enumerate(atom.binding_terms):
            offset, end = next(ranges)
            parts.extend(
                f"mode_aggregate_condition_arg({mode.id},{condition},{argument},{flat_position})."
                for flat_position in range(offset, end)
            )
            offset = end
    offset, end = next(ranges)
    parts.extend(
        f"mode_aggregate_result_arg({mode.id},{position})."
        for position in range(offset, end)
    )
    return parts


def _head_aggregate_facts(
    mode: ClauseMode,
    element: HeadAggregateElement,
    predicate_ids: dict[Predicate, int],
) -> list[str]:
    parts: list[str] = []
    offset = 0
    ranges = iter(zip(mode.argument_offsets, mode.argument_offsets[1:]))
    for term in (*element.terms, *element.conclusion.arguments):
        offset, end = next(ranges)
        for position in range(offset, end):
            parts.append(f"head_aggregate_element_arg({mode.id},{position}).")
        offset = end
    for condition, literal in enumerate(element.conditions):
        if isinstance(literal, AtomLiteral) and not literal.default_negated:
            parts.extend(_local_pool_facts(
                mode.id, "head_aggregate", 0, condition, offset, literal.atom,
            ))
        if isinstance(literal, ComparisonLiteral):
            parts.extend(_local_comparison_facts(
                mode.id, "head_aggregate", 0, condition, offset, literal,
            ))
        if isinstance(literal, AtomLiteral):
            parts.append(
                f"head_aggregate_condition_atom({mode.id},{condition},{predicate_ids[literal.atom.signature]})."
            )
        for term in literal.arguments:
            offset, end = next(ranges)
            for position in range(offset, end):
                parts.append(f"head_aggregate_element_arg({mode.id},{position}).")
                if isinstance(literal, AtomLiteral) and not literal.default_negated:
                    parts.append(
                        f"head_aggregate_positive_condition_arg({mode.id},{condition},{position})."
                    )
            offset = end
    parts.append(f"mode_condition_count({mode.id},{len(element.conditions)}).")
    return parts


def _local_pool_facts(
    mode: int,
    scope: str,
    element: int,
    condition: int,
    offset: int,
    atom: AtomTemplate,
) -> list[str]:
    alternatives = _pool_alternative_positions(atom)
    if not _binds_partially(alternatives, atom):
        return []
    parts = [
        f"local_pool_condition_arg({mode},{scope},{element},{condition},{position})."
        for position in range(offset, offset + len(atom.bindings()))
    ]
    for alternative, positions in enumerate(alternatives):
        parts.append(
            f"local_pool_alternative({mode},{scope},{element},{condition},{alternative})."
        )
        parts.extend(
            f"local_pool_alternative_arg({mode},{scope},{element},{condition},{alternative},{offset + position})."
            for position in sorted(positions)
        )
    return parts


def _local_comparison_facts(
    mode: int,
    scope: str,
    element: int,
    condition: int,
    offset: int,
    literal: ComparisonLiteral,
) -> list[str]:
    if literal.default_negated:
        return []
    bindings = tuple(binding for term in literal.terms for binding in mode_terms.bindings(term))
    positions = range(len(bindings))
    parts: list[str] = []
    variant = 0
    for size in range(1, len(bindings) + 1):
        for outputs in combinations(positions, size):
            directions = tuple(
                "output" if index in outputs else "input" for index in positions
            )
            if not _comparison_outputs_are_safe(
                _with_binding_directions(literal, directions)
            ):
                continue
            inputs = tuple(index for index in positions if index not in outputs)
            parts.append(
                f"local_comparison_variant({mode},{scope},{element},{condition},{variant},{len(inputs)})."
            )
            parts.extend(
                f"local_comparison_input({mode},{scope},{element},{condition},{variant},{offset + index})."
                for index in inputs
            )
            parts.extend(
                f"local_comparison_output({mode},{scope},{element},{condition},{variant},{offset + index})."
                for index in outputs
            )
            variant += 1
    return parts


def _operands_are_interchangeable(literal: ArithmeticLiteral) -> bool:
    return _terms_are_interchangeable(*literal.arguments[:-1])


def _atom_arguments_are_interchangeable(atom: AtomTemplate) -> bool:
    """Whether a binary atom of plain variables admits both argument orders."""
    return (
        not atom.alternatives
        and len(atom.terms) == 2
        and all(mode_terms.kind(term) == "variable" for term in atom.terms)
        and _terms_are_interchangeable(*atom.terms)
    )


def _terms_are_interchangeable(left: ast.AST, right: ast.AST) -> bool:
    """Whether swapping two single-variable terms yields the same template."""
    left_bindings = mode_terms.bindings(left)
    right_bindings = mode_terms.bindings(right)
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
