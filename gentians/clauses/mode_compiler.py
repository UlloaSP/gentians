from collections.abc import Iterator
from dataclasses import replace
from itertools import product

from clingo import ast

from ..language import terms as mode_terms
from ..language.ast_nodes import LOCATION, binding_term
from ..language.ir.aggregate_literal import AggregateLiteral
from .arithmetic_literal import ArithmeticLiteral
from ..language.ir.atom_literal import AtomLiteral
from ..language.ir.boolean_literal import BooleanLiteral
from ..language.ir.comparison_literal import ComparisonLiteral
from ..language.ir.conditional_literal import ConditionalLiteral
from ..language.ir.head_template import HeadTemplate
from ..language.ir.inductive_task import InductiveTask
from ..language.ir.mode_declaration import ModeDeclaration
from .clause_mode import ClauseMode


type _Conditionable = AtomLiteral | BooleanLiteral | ComparisonLiteral | ConditionalLiteral


def _bounded_combinations(
    groups: tuple[tuple[int, ...], ...],
    capacities: tuple[int, ...],
    length: int,
) -> Iterator[tuple[int, ...]]:
    """Yield lexicographic combinations, pruning exhausted groups before descent."""
    counts = [0] * len(capacities)
    selected: list[int] = []
    index = 0
    while True:
        if len(selected) == length:
            yield tuple(selected)
        elif index < len(groups):
            if all(counts[group] < capacities[group] for group in groups[index]):
                selected.append(index)
                for group in groups[index]:
                    counts[group] += 1
                continue
            index += 1
            continue
        if not selected:
            return
        previous = selected.pop()
        for group in groups[previous]:
            counts[group] -= 1
        index = previous + 1


class _Conditions:
    """Condition alternatives shared by the modes of one inductive task."""

    __slots__ = ("limit", "modes", "groups", "capacities", "_variants")

    def __init__(self, task: InductiveTask) -> None:
        self.limit = _condition_limit(task)
        self.modes = tuple(
            (literal, group)
            for group, declaration in enumerate(task.language_bias_condition)
            for literal in declaration.literal.concretizations(task.constants)
            if isinstance(literal, AtomLiteral | ComparisonLiteral)
        )
        capacities = [
            self.limit if declaration.recall < 0 else declaration.recall
            for declaration in task.language_bias_condition
        ]
        groups: list[tuple[int, ...]] = []
        for literal, group in self.modes:
            if any(mode_terms.bindings(term) for term in literal.arguments):
                groups.append((group,))
            else:
                groups.append((group, len(capacities)))
                capacities.append(1)
        self.groups = tuple(groups)
        self.capacities = tuple(capacities)
        self._variants: dict[_Conditionable, tuple[_Conditionable, ...]] = {}

    def expand(self, conclusion: _Conditionable) -> tuple[_Conditionable, ...]:
        if conclusion not in self._variants:
            self._variants[conclusion] = self._expand(conclusion)
        return self._variants[conclusion]

    def _expand(self, conclusion: _Conditionable) -> tuple[_Conditionable, ...]:
        if isinstance(conclusion, ComparisonLiteral) and any(
            binding.direction == "output"
            for term in conclusion.arguments
            for binding in mode_terms.bindings(term)
        ):
            return (conclusion,)
        literals: list[_Conditionable] = [conclusion]
        conditional = isinstance(conclusion, ConditionalLiteral)
        base_conclusion = conclusion.conclusion if conditional else conclusion
        base_conditions = conclusion.conditions if conditional else ()
        base_groups = conclusion.condition_groups if conditional else ()
        remaining = max(0, self.limit - len(base_conditions))
        for length in range(1, remaining + 1):
            for indices in _bounded_combinations(self.groups, self.capacities, length):
                selected = tuple(self.modes[index] for index in indices)
                literals.append(
                    ConditionalLiteral(
                        base_conclusion,
                        (*base_conditions, *(literal for literal, _ in selected)),
                        (*base_groups, *(group for _, group in selected)),
                    )
                )
        return tuple(literals)


def _combined_head_templates(
    task: InductiveTask,
    declarations: list[ModeDeclaration],
    kind: str,
    conditions: _Conditions,
) -> tuple[HeadTemplate, ...]:
    if not declarations:
        return ()

    max_width = task.max_head_literals
    if max_width is None:
        if any(declaration.recall < 0 for declaration in declarations):
            directive = "#modeha" if kind == "choice" else "#modehd"
            raise ValueError(f"#maxhl(*) requires finite recalls for every {directive}")
        aggregate_capacity = sum(declaration.recall for declaration in declarations)
        max_width = max(
            aggregate_capacity,
            max((head.width for head in task.language_bias_head), default=0),
        )
    if all(declaration.recall >= 0 for declaration in declarations):
        max_width = min(max_width, sum(mode.recall for mode in declarations))

    choices = tuple(
        (
            declaration_index,
            AtomLiteral(
                atom,
                declaration.literal.default_negated,
                declaration.literal.double_negated,
            ),
        )
        for declaration_index, declaration in enumerate(declarations)
        if isinstance(declaration.literal, AtomLiteral)
        for atom in declaration.literal.atom.concretizations(task.constants)
    )
    atom_capacities = {
        literal: _aggregate_head_atom_capacity(
            task, literal, max_width, conditions
        )
        for _declaration_index, literal in choices
    }
    max_width = min(max_width, sum(atom_capacities.values()))
    declaration_capacities = {
        index: sum(
            atom_capacities[literal]
            for declaration_index, literal in choices
            if declaration_index == index
        )
        for index in range(len(declarations))
    }
    max_width = min(
        max_width,
        sum(
            capacity
            if declarations[index].recall < 0
            else min(capacity, declarations[index].recall)
            for index, capacity in declaration_capacities.items()
        ),
    )
    literals = tuple(atom_capacities)
    literal_groups = {literal: len(declarations) + index for index, literal in enumerate(literals)}
    groups = tuple((index, literal_groups[literal]) for index, literal in choices)
    capacities = (
        *(max_width if mode.recall < 0 else mode.recall for mode in declarations),
        *(atom_capacities[literal] for literal in literals),
    )
    templates: list[HeadTemplate] = []
    seen: set[HeadTemplate] = set()
    minimum = max(2 if kind == "disjunction" else 1, task.min_aggregate_head_literals)
    for width in range(minimum, max_width + 1):
        bounds = _aggregate_head_bounds(width) if kind == "choice" else ((None, None),)
        for indices in _bounded_combinations(groups, capacities, width):
            combination = tuple(choices[index] for index in indices)
            elements = tuple(literal for _index, literal in combination)
            for lower, upper in bounds:
                form = (
                    ast.Aggregate(
                        LOCATION,
                        ast.Guard(
                            ast.ComparisonOperator.LessEqual, binding_term(str(lower))
                        ),
                        [],
                        ast.Guard(
                            ast.ComparisonOperator.LessEqual, binding_term(str(upper))
                        ),
                    )
                    if kind == "choice"
                    else ast.Disjunction(LOCATION, [])
                )
                template = HeadTemplate(form, elements)
                if template not in seen:
                    seen.add(template)
                    templates.append(template)
    return tuple(templates)


def _aggregate_head_atom_capacity(
    task: InductiveTask,
    literal: AtomLiteral,
    max_width: int,
    conditions: _Conditions,
) -> int:
    variants = tuple(
        variant
        for variant in conditions.expand(literal)
        if isinstance(variant, AtomLiteral | ConditionalLiteral)
    )
    return min(
        max_width,
        sum(
            _literal_assignment_capacity(task, variant, max_width)
            for variant in variants
        ),
    )


def _literal_assignment_capacity(
    task: InductiveTask,
    literal: AtomLiteral | ConditionalLiteral,
    max_width: int,
) -> int:
    binding_count = sum(len(mode_terms.bindings(term)) for term in literal.arguments)
    if not binding_count:
        return 1
    if task.max_variables is None:
        return max_width
    return task.max_variables**binding_count


def _aggregate_head_bounds(width: int) -> tuple[tuple[int, int], ...]:
    return tuple(
        (lower, upper)
        for lower in range(width + 1)
        for upper in range(max(1, lower), width + 1)
        if not (lower == upper == width)
        and not (width > 1 and lower == 0 and upper == width)
    )


def _clause_modes(
    task: InductiveTask,
) -> list[ClauseMode]:
    modes: list[ClauseMode] = []
    next_id = 0

    def add(mode: ClauseMode) -> None:
        nonlocal next_id
        modes.append(mode)
        next_id += 1

    conditions = _Conditions(task)
    condition_limit = conditions.limit
    next_head_form = 0
    head_templates = tuple(
        concrete
        for template in (
            *task.language_bias_head,
            *_combined_head_templates(task, task.language_bias_aggregate_head, "choice", conditions),
            *_combined_head_templates(task, task.language_bias_disjunctive_head, "disjunction", conditions),
        )
        for concrete in template.concretizations(task.constants)
    )
    for head in head_templates:
        if head.kind == "aggregate":
            form_id = next_head_form
            next_head_form += 1
            if not head.elements:
                add(
                    ClauseMode(
                        id=next_id,
                        recall_group=next_id,
                        section="head",
                        recall=1,
                        literal=BooleanLiteral(True),
                        head_form=form_id,
                        head_position=0,
                        head=head,
                    )
                )
            for position, element in enumerate(head.elements):
                add(
                    ClauseMode(
                        id=next_id,
                        recall_group=next_id,
                        section="head",
                        recall=1,
                        literal=element,
                        head_form=form_id,
                        head_position=position,
                        head=head,
                    )
                )
            continue
        concrete_literals_base = tuple(
            element
            for element in head.elements
            if isinstance(
                element,
                AtomLiteral | BooleanLiteral | ComparisonLiteral | ConditionalLiteral,
            )
        )
        if not concrete_literals_base:
            form_id = next_head_form
            next_head_form += 1
            add(
                ClauseMode(
                    id=next_id,
                    recall_group=next_id,
                    section="head",
                    recall=1,
                    literal=BooleanLiteral(True),
                    head_form=form_id,
                    head_position=0,
                    head=head,
                )
            )
            continue
        alternatives = tuple(
            conditions.expand(literal)
            for literal in concrete_literals_base
        )
        for concrete_literals in product(*alternatives):
            generated_conditions = sum(
                sum(group >= 0 for group in literal.condition_groups)
                for literal in concrete_literals
                if isinstance(literal, ConditionalLiteral)
            )
            if generated_conditions > condition_limit:
                continue
            if (
                sum(
                    len(literal.conditions)
                    for literal in concrete_literals
                    if isinstance(literal, ConditionalLiteral)
                )
                > (task.max_body_literals or 0)
                and task.max_body_literals is not None
            ):
                continue
            form_id = next_head_form
            next_head_form += 1
            for position, literal in enumerate(concrete_literals):
                add(
                    ClauseMode(
                        id=next_id,
                        recall_group=next_id,
                        section="head",
                        recall=1,
                        literal=literal,
                        head_form=form_id,
                        head_position=position,
                        head=head,
                    )
                )

    body_literals = tuple(
        (
            declaration,
            tuple(
                _specialize_body_literal(literal)
                for conclusion in declaration.literal.concretizations(task.constants)
                for literal in (
                    (conclusion,)
                    if isinstance(conclusion, AggregateLiteral | ArithmeticLiteral)
                    else conditions.expand(conclusion)
                )
            ),
        )
        for declaration in task.language_bias_body
    )
    additive_recalls: dict[str, list[int]] = {}
    additive_operators: dict[str, set[str]] = {}
    for declaration, literals in body_literals:
        declaration_families: set[str] = set()
        for literal in literals:
            if (family := _implicit_additive_family(literal)) is not None:
                assert isinstance(literal, ArithmeticLiteral)
                declaration_families.add(family)
                additive_operators.setdefault(family, set()).add(literal.operator)
        for family in declaration_families:
            additive_recalls.setdefault(family, []).append(declaration.recall)

    merged_additive_families = {
        family
        for family, operators in additive_operators.items()
        if operators == {"+", "-"}
    }

    emitted_additive_families: set[str] = set()
    for declaration, literals in body_literals:
        recall_group = next_id
        for literal in literals:
            family = _implicit_additive_family(literal)
            if family in merged_additive_families:
                if family in emitted_additive_families:
                    continue
                emitted_additive_families.add(family)
                assert isinstance(literal, ArithmeticLiteral)
                literal = _canonical_additive_literal(literal)
                recall = _combined_recall(additive_recalls[family])
            else:
                recall = declaration.recall
            add(
                ClauseMode(
                    id=next_id,
                    recall_group=recall_group,
                    section="body",
                    recall=recall,
                    literal=literal,
                )
            )

    return modes


def _condition_limit(task: InductiveTask) -> int:
    if not task.language_bias_condition:
        return 0
    if task.max_body_literals is not None:
        return task.max_body_literals
    if any(mode.recall < 0 for mode in task.language_bias_condition):
        raise ValueError("#maxbl(*) requires finite recalls for every condition mode")
    return sum(mode.recall for mode in task.language_bias_condition)


def _specialize_body_literal(
    literal: AggregateLiteral
    | AtomLiteral
    | BooleanLiteral
    | ComparisonLiteral
    | ConditionalLiteral
    | ArithmeticLiteral,
) -> (
    AggregateLiteral
    | AtomLiteral
    | BooleanLiteral
    | ComparisonLiteral
    | ConditionalLiteral
    | ArithmeticLiteral
):
    if (
        not isinstance(literal, ComparisonLiteral)
        or literal.default_negated
        or literal.operators != ("=",)
        or len(literal.terms) != 2
    ):
        return literal
    expression, output = literal.terms
    inputs = mode_terms.arguments(expression)
    if (expression.ast_type == ast.ASTType.UnaryOperation
        and expression.operator_type == ast.UnaryOperator.Absolute
        and expression.argument.ast_type == ast.ASTType.BinaryOperation
        and expression.argument.operator_type == ast.BinaryOperator.Minus):
        inputs = mode_terms.arguments(expression.argument)
    if (
        mode_terms.kind(expression) != "arithmetic"
        or len(inputs) != 2
        or any(mode_terms.kind(argument) != "variable" for argument in inputs)
        or mode_terms.kind(output) != "variable"
        or mode_terms.binding(output).direction != "output"
    ):
        return literal
    return ArithmeticLiteral(
        expression,
        output,
        implicit_additive_family_member=(
            literal.fully_implicit_directions and mode_terms.value(expression) in {"+", "-"}
        ),
    )


def _implicit_additive_family(
    literal: AggregateLiteral
    | AtomLiteral
    | BooleanLiteral
    | ComparisonLiteral
    | ConditionalLiteral
    | ArithmeticLiteral,
) -> str | None:
    if (
        not isinstance(literal, ArithmeticLiteral)
        or not literal.implicit_additive_family_member
        or literal.operator not in {"+", "-"}
        or any(mode_terms.kind(term) != "variable" for term in literal.arguments)
    ):
        return None
    bindings = tuple(binding for term in literal.arguments for binding in mode_terms.bindings(term))
    if (
        len(bindings) != 3
        or len({binding.type for binding in bindings}) != 1
        or bindings[0].type != "numeric"
        or tuple(binding.direction for binding in bindings)
        != ("input", "input", "output")
        or any(binding.label for binding in bindings)
    ):
        return None
    return bindings[0].type


def _canonical_additive_literal(literal: ArithmeticLiteral) -> ArithmeticLiteral:
    return replace(
        literal,
        expression=literal.expression.update(operator_type=ast.BinaryOperator.Plus),
    )


def _combined_recall(recalls: list[int]) -> int:
    return -1 if any(recall < 0 for recall in recalls) else sum(recalls)


def _section_capacity(limit: int | None, modes: list[ClauseMode], section: str) -> int:
    if limit is not None:
        return limit
    if section == "head":
        return max(
            (mode.head_position + 1 for mode in modes if mode.section == "head"),
            default=0,
        )
    recalls: dict[int, int] = {}
    for mode in modes:
        if mode.section != section:
            continue
        if mode.recall < 0:
            directive = "#maxhl" if section == "head" else "#maxbl"
            raise ValueError(
                f"{directive}(*) requires finite recalls for every {section} mode"
            )
        recalls[mode.recall_group] = min(
            recalls.get(mode.recall_group, mode.recall), mode.recall
        )
    return sum(recalls.values())
