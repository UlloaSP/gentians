from collections import Counter
from collections.abc import Iterable
from itertools import combinations_with_replacement, product


from ..language.ir.aggregate_declaration import AggregateDeclaration
from ..language.ir.aggregate_literal import AggregateLiteral
from ..language.ir.arithmetic_literal import ArithmeticLiteral
from ..language.ir.atom_literal import AtomLiteral
from ..language.ir.atom_template import AtomTemplate
from ..language.ir.comparison_literal import ComparisonLiteral
from ..language.ir.conditional_literal import ConditionalLiteral
from ..language.ir.head_template import HeadTemplate
from .clause_capabilities import ClauseCapabilities
from .clause_mode import ClauseMode
from ..language.ir.mode_declaration import ModeDeclaration
from ..language.ir.operator_declaration import OperatorDeclaration
from ..language.asp import (
    Predicate,
)
from ..language.ir.inductive_task import InductiveTask
from ..language.ir.term_template import TermTemplate
from .task_analysis import _head_atoms, _mode_atom_literals

def _combined_head_templates(
    task: InductiveTask,
    declarations: list[ModeDeclaration],
    kind: str,
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
        (declaration_index, atom)
        for declaration_index, declaration in enumerate(declarations)
        if isinstance(declaration.literal, AtomLiteral)
        for atom in declaration.literal.atom.concretizations(task.constants)
    )
    condition_limit = _condition_limit(task)
    condition_modes = _condition_modes(task) if condition_limit else ()
    atom_capacities = {
        atom: _aggregate_head_atom_capacity(
            task, atom, max_width, condition_modes, condition_limit
        )
        for _declaration_index, atom in choices
    }
    max_width = min(max_width, sum(atom_capacities.values()))
    declaration_capacities = {
        index: sum(
            atom_capacities[atom]
            for declaration_index, atom in choices
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
    templates: list[HeadTemplate] = []
    seen: set[HeadTemplate] = set()
    minimum = max(
        2 if kind == "disjunction" else 1, task.min_aggregate_head_literals
    )
    for width in range(minimum, max_width + 1):
        for combination in combinations_with_replacement(choices, width):
            declaration_counts = Counter(index for index, _atom in combination)
            if any(
                declarations[index].recall >= 0 and count > declarations[index].recall
                for index, count in declaration_counts.items()
            ):
                continue
            if any(
                count > atom_capacities[atom]
                for atom, count in Counter(atom for _index, atom in combination).items()
            ):
                continue
            elements = tuple(atom for _index, atom in combination)
            bounds = (
                _aggregate_head_bounds(width) if kind == "choice" else ((None, None),)
            )
            for lower, upper in bounds:
                template = HeadTemplate(kind, elements, lower, upper)
                if template not in seen:
                    seen.add(template)
                    templates.append(template)
    return tuple(templates)


def _aggregate_head_templates(task: InductiveTask) -> tuple[HeadTemplate, ...]:
    return _combined_head_templates(
        task, task.language_bias_aggregate_head, "choice"
    )


def _disjunctive_head_templates(task: InductiveTask) -> tuple[HeadTemplate, ...]:
    return _combined_head_templates(
        task, task.language_bias_disjunctive_head, "disjunction"
    )


def _aggregate_head_atom_capacity(
    task: InductiveTask,
    atom: AtomTemplate,
    max_width: int,
    condition_modes: tuple[tuple[AtomLiteral | ComparisonLiteral, int, int], ...],
    condition_limit: int,
) -> int:
    variants = tuple(
        variant
        for variant in _conditioned_literals(
            AtomLiteral(atom), condition_modes, condition_limit
        )
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
    binding_count = sum(len(term.bindings()) for term in literal.arguments)
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
    capabilities: ClauseCapabilities,
    predicate_arg_types: dict[tuple[str, int, int], str],
    aggregate_specs: list[AggregateDeclaration],
) -> list[ClauseMode]:
    modes: list[ClauseMode] = []
    next_id = 0

    def add(mode: ClauseMode) -> None:
        nonlocal next_id
        modes.append(mode)
        next_id += 1

    condition_limit = _condition_limit(task)
    condition_modes = _condition_modes(task)
    next_head_form = 0
    head_templates = (
        *((declaration.template, False) for declaration in task.language_bias_head),
        *((template, True) for template in _aggregate_head_templates(task)),
        *((template, False) for template in _disjunctive_head_templates(task)),
    )
    for template, aggregate_head in head_templates:
        concrete_elements = []
        for atom, exact_conditions in zip(
            template.elements, template.conditions, strict=True
        ):
            base: AtomLiteral | ConditionalLiteral = AtomLiteral(atom)
            if exact_conditions:
                base = ConditionalLiteral(
                    base,
                    exact_conditions,
                    (-1,) * len(exact_conditions),
                )
            concrete_elements.append(
                tuple(
                    literal
                    for literal in _literal_concretizations(base, task.constants)
                    if isinstance(literal, AtomLiteral | ConditionalLiteral)
                )
            )
        for concrete_literals_base in product(*concrete_elements):
            concrete_form = tuple(
                literal.conclusion.atom
                if isinstance(literal, ConditionalLiteral)
                else literal.atom
                for literal in concrete_literals_base
            )
            head = HeadTemplate(
                template.kind,
                concrete_form,
                template.lower,
                template.upper,
            )
            alternatives = tuple(
                _conditioned_literals(literal, condition_modes, condition_limit)
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
                            aggregate_head=aggregate_head,
                        )
                    )

    for declaration in task.language_bias_body:
        recall_group = next_id
        for conclusion in _literal_concretizations(
            declaration.literal, task.constants
        ):
            for literal in _conditioned_literals(
                conclusion, condition_modes, condition_limit
            ):
                add(
                    ClauseMode(
                        id=next_id,
                        recall_group=recall_group,
                        section="body",
                        recall=declaration.recall,
                        literal=literal,
                    )
                )

    operator_modes = [
        declaration
        for declaration in task.arithmetic_modes
        if isinstance(declaration, OperatorDeclaration)
    ]
    for declaration in (
        declaration
        for declaration in task.arithmetic_modes
        if isinstance(declaration, ModeDeclaration)
    ):
        recall_group = next_id
        for literal in _literal_concretizations(declaration.literal, task.constants):
            add(
                ClauseMode(
                    id=next_id,
                    recall_group=recall_group,
                    section="body",
                    recall=declaration.recall,
                    literal=literal,
                )
            )

    emitted_comparison_families: set[frozenset[str]] = set()
    for declaration in operator_modes:
        if declaration.operator not in {"eq", "neq", "lt", "leq", "gt", "geq"}:
            continue
        if declaration.operator == "eq":
            symbol = "="
            family = frozenset(("eq",))
        elif declaration.operator in {"lt", "gt"}:
            family = frozenset(("lt", "gt"))
            symbol = "<"
        elif declaration.operator in {"leq", "geq"}:
            family = frozenset(("leq", "geq"))
            symbol = "<="
        else:
            family = frozenset((declaration.operator,))
            symbol = {"neq": "!="}.get(declaration.operator)
        if family in emitted_comparison_families:
            continue
        emitted_comparison_families.add(family)
        numeric = declaration.operator in {"lt", "leq", "gt", "geq"}
        if symbol and (
            numeric
            and capabilities.allow_numeric_comparison
            or declaration.operator == "neq"
            and capabilities.allow_equality_comparison
            or declaration.operator == "eq"
            and capabilities.allow_equality_comparison
        ):
            add(
                ClauseMode(
                    id=next_id,
                    recall_group=next_id,
                    section="body",
                    recall=_combined_recall(
                        candidate.recall
                        for candidate in operator_modes
                        if candidate.operator in family
                    ),
                    literal=ComparisonLiteral(
                        symbol,
                        (
                            TermTemplate.variable("numeric" if numeric else "any", ""),
                            TermTemplate.variable("numeric" if numeric else "any", ""),
                        ),
                    ),
                )
            )

    if capabilities.allow_arithmetic:
        additive = [
            declaration
            for declaration in operator_modes
            if declaration.operator in {"add", "sub"}
        ]
        if additive:
            recall = (
                -1
                if any(declaration.recall < 0 for declaration in additive)
                else sum(declaration.recall for declaration in additive)
            )
            add(
                ClauseMode(
                    id=next_id,
                    recall_group=next_id,
                    section="body",
                    recall=recall,
                    literal=ArithmeticLiteral(
                        TermTemplate(
                            "arithmetic",
                            "+",
                            (
                                TermTemplate.variable("numeric", ""),
                                TermTemplate.variable("numeric", ""),
                            ),
                        ),
                        TermTemplate.variable("numeric", ""),
                    ),
                )
            )
        for declaration in operator_modes:
            if declaration.operator in {"add", "sub"}:
                continue
            symbol = {
                "mul": "*",
                "div": "/",
                "mod": "\\",
                "abs": "abs",
            }.get(declaration.operator)
            if symbol:
                add(
                    ClauseMode(
                        id=next_id,
                        recall_group=next_id,
                        section="body",
                        recall=declaration.recall,
                        literal=ArithmeticLiteral(
                            TermTemplate(
                                "arithmetic",
                                symbol,
                                (
                                    TermTemplate.variable("numeric", ""),
                                    TermTemplate.variable("numeric", ""),
                                ),
                            ),
                            TermTemplate.variable("numeric", ""),
                        ),
                    )
                )

    for declaration in aggregate_specs:
        atoms = list(declaration.atoms)
        total_atom_arity = sum(arity for _, arity in atoms)
        tuple_arities = (
            range(1, total_atom_arity + 1)
            if declaration.unbalanced
            else [total_atom_arity]
        )
        recall_group = next_id
        for tuple_arity in tuple_arities:
            conditions = tuple(
                AtomTemplate(
                    name.removeprefix("-"),
                    tuple(
                        TermTemplate.variable(
                            predicate_arg_types.get(
                                (name.removeprefix("-"), arity, arg), "any"
                            ),
                            "",
                        )
                        for arg in range(arity)
                    ),
                    name.startswith("-"),
                )
                for name, arity in atoms
            )
            add(
                ClauseMode(
                    id=next_id,
                    recall_group=recall_group,
                    section="body",
                    recall=declaration.recall,
                    literal=AggregateLiteral(
                        declaration.function,
                        tuple(
                            TermTemplate.variable("any", "") for _ in range(tuple_arity)
                        ),
                        conditions,
                        TermTemplate.variable("numeric", ""),
                    ),
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


def _condition_modes(
    task: InductiveTask,
) -> tuple[tuple[AtomLiteral | ComparisonLiteral, int, int], ...]:
    return tuple(
        (literal, group, declaration.recall)
        for group, declaration in enumerate(task.language_bias_condition)
        for literal in _literal_concretizations(declaration.literal, task.constants)
        if isinstance(literal, AtomLiteral | ComparisonLiteral)
    )


def _conditioned_literals(
    conclusion: AtomLiteral | ComparisonLiteral | ConditionalLiteral,
    condition_modes: tuple[tuple[AtomLiteral | ComparisonLiteral, int, int], ...],
    limit: int,
) -> tuple[AtomLiteral | ComparisonLiteral | ConditionalLiteral, ...]:
    if isinstance(conclusion, ComparisonLiteral):
        return (conclusion,)
    literals: list[AtomLiteral | ComparisonLiteral | ConditionalLiteral] = [conclusion]
    base_conclusion = (
        conclusion.conclusion
        if isinstance(conclusion, ConditionalLiteral)
        else conclusion
    )
    base_conditions = (
        conclusion.conditions if isinstance(conclusion, ConditionalLiteral) else ()
    )
    base_groups = (
        conclusion.condition_groups
        if isinstance(conclusion, ConditionalLiteral)
        else ()
    )
    remaining = max(0, limit - len(base_conditions))
    for length in range(1, remaining + 1):
        for indices in combinations_with_replacement(
            range(len(condition_modes)), length
        ):
            selected = tuple(condition_modes[index] for index in indices)
            if any(
                sum(
                    candidate_group == group
                    for _literal, candidate_group, _ in selected
                )
                > recall
                for _literal, group, recall in selected
                if recall >= 0
            ):
                continue
            if any(
                indices.count(index) > 1
                and not any(
                    term.bindings() for term in condition_modes[index][0].arguments
                )
                for index in set(indices)
            ):
                continue
            literals.append(
                ConditionalLiteral(
                    base_conclusion,
                    (
                        *base_conditions,
                        *(literal for literal, _group, _recall in selected),
                    ),
                    (*base_groups, *(group for _literal, group, _recall in selected)),
                )
            )
    return tuple(literals)


def _literal_concretizations(
    literal: AtomLiteral | ComparisonLiteral | ConditionalLiteral,
    constants: dict[str, tuple[str, ...]],
) -> tuple[AtomLiteral | ComparisonLiteral | ConditionalLiteral, ...]:
    if isinstance(literal, AtomLiteral):
        return tuple(
            AtomLiteral(atom, literal.default_negated)
            for atom in literal.atom.concretizations(constants)
        )
    if isinstance(literal, ConditionalLiteral):
        return literal.concretizations(constants)
    return tuple(
        ComparisonLiteral(literal.operator, (terms[0], terms[1]), literal.family)
        for terms in product(
            *(term.concretizations(constants) for term in literal.terms)
        )
    )


def _combined_recall(recalls: Iterable[int]) -> int:
    values = tuple(recalls)
    return -1 if any(recall < 0 for recall in values) else sum(values)


def _variable_arity(mode: ClauseMode) -> int:
    return len(mode.bindings)


def _binding_positions(mode: ClauseMode) -> tuple[int, ...]:
    if isinstance(
        mode.literal, ConditionalLiteral | ComparisonLiteral | ArithmeticLiteral
    ) or (
        isinstance(mode.literal, AtomLiteral)
        and any(term.kind in {"function", "tuple"} for term in mode.literal.atom.terms)
    ):
        return tuple(range(len(mode.bindings)))
    return tuple(binding.path[0] for binding in mode.bindings)


def _section_capacity(
    limit: int | None, modes: list[ClauseMode], section: str
) -> int:
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


def _closed_body_predicates(task: InductiveTask) -> set[Predicate]:
    head_predicates = {atom.signature for atom in _head_atoms(task)}
    return {
        literal.atom.signature
        for mode in (*task.language_bias_body, *task.language_bias_condition)
        for literal in _mode_atom_literals(mode)
        if literal.atom.signature not in head_predicates
    }
