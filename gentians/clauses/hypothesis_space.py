import re
from collections import Counter
from collections.abc import Iterable
from itertools import combinations, combinations_with_replacement, permutations, product
from pathlib import Path

import clingo
from clingo import ast

from ..arguments import Arguments
from ..asp.callbacks import wrapper_exit_callback
from ..asp.stats import clingo_stat, ground_stats
from ..timing import (
    add,
    current_phase,
    instrumentation,
    metric_enabled,
    net_time,
    profile_phase,
    record_metric,
)
from ..language.ir.aggregate_declaration import AggregateDeclaration
from ..language.ir.aggregate_literal import AggregateLiteral
from ..language.ir.arithmetic_literal import ArithmeticLiteral
from .arithmetic_system import ArithmeticSystemKey, canonical_arithmetic_clause
from ..language.ir.atom_literal import AtomLiteral
from ..language.ir.atom_template import AtomTemplate
from .closed_world_properties import ClosedWorldProperties
from ..language.ir.comparison_literal import ComparisonLiteral
from ..language.ir.conditional_literal import ConditionalLiteral
from ..language.ir.head_template import HeadTemplate
from .hypothesis_capabilities import HypothesisCapabilities
from .hypothesis_mode import HypothesisMode
from .linear_constraint import LinearConstraint
from ..language.ir.mode_declaration import ModeDeclaration
from ..language.ir.operator_declaration import OperatorDeclaration
from ..language.asp import (
    Predicate,
    add_program,
    clause_predicates,
    fragment_atoms,
    parse_rule,
    render_program,
)
from ..language.ir.inductive_task import InductiveTask
from .reified_clause import ReifiedClause
from .reified_literal import ReifiedLiteral
from .rule_entry import RuleEntry
from .rule_space import RuleSpace
from ..language.ir.term_template import TermTemplate

HYPOTHESIS_SPACE_RULE_MODULES = (
    "core/slots.lp",
    "core/limits.lp",
    "core/constraints.lp",
    "core/recall.lp",
    "core/arguments.lp",
    "core/head_labels.lp",
    "core/literals.lp",
    "core/conditionals.lp",
    "core/bias.lp",
    "core/tuple_helpers.lp",
    "aggregates/roles.lp",
    "safety/linkedness.lp",
    "safety/typing.lp",
    "safety/variables.lp",
    "safety/asp_safety.lp",
    "safety/mode_directed.lp",
    "operators/comparisons.lp",
    "operators/arithmetic.lp",
    "operators/arithmetic_domain.lp",
    "aggregates/canonicalization.lp",
    "aggregates/safety.lp",
    "aggregates/duplicates.lp",
    "properties/arg_equal.lp",
    "properties/arg_distinct.lp",
    "properties/symmetric.lp",
    "properties/asymmetric.lp",
    "properties/strict_order.lp",
    "properties/equivalent.lp",
    "properties/inverse.lp",
    "properties/disjoint.lp",
    "properties/universal.lp",
    "properties/empty.lp",
    "properties/partition.lp",
    "properties/key.lp",
    "properties/reflexive.lp",
    "properties/total_order.lp",
    "properties/subsumption.lp",
    "properties/irreflexive.lp",
    "properties/antisymmetric.lp",
    "properties/implies.lp",
    "properties/project_implies.lp",
    "properties/complement.lp",
    "properties/mutex.lp",
    "properties/functional.lp",
    "properties/functional_set.lp",
    "properties/cardinality_upper.lp",
    "properties/transitive.lp",
    "properties/acyclic.lp",
    "core/coherence.lp",
    "core/duplicates.lp",
)
HYPOTHESIS_SPACE_RULES = "\n".join(
    (Path(__file__).with_name("rules") / module).read_text()
    for module in HYPOTHESIS_SPACE_RULE_MODULES
)

_ValueLiteral = tuple[int, int]
_ModeLiteral = tuple[int, tuple[int, ...], int]
_ModelSlot = tuple[
    str,
    int,
    tuple[_ModeLiteral, ...],
    tuple[tuple[_ValueLiteral, ...], ...],
]


def _rule_entry_from_clause(
    rendered: str,
    clause: ReifiedClause,
    modes: dict[int, HypothesisMode],
) -> RuleEntry:
    heads: set[Predicate] = set()
    deps: set[Predicate] = set()
    for literal in clause.head:
        mode = modes[literal.mode_id]
        if isinstance(mode.literal, AtomLiteral):
            heads.add(mode.literal.atom.signature)
        elif isinstance(mode.literal, ConditionalLiteral):
            heads.add(mode.literal.conclusion.atom.signature)
            deps.update(
                predicate
                for condition in mode.literal.conditions
                for predicate in condition.dependencies
            )
    for literal in clause.body:
        mode = modes[literal.mode_id]
        deps.update(mode.dependencies)
    body_literals = len(clause.body) + sum(
        modes[literal.mode_id].condition_count
        for literal in (*clause.head, *clause.body)
    )
    return RuleEntry(
        rendered,
        parse_rule(rendered),
        frozenset(heads),
        frozenset(deps),
        body_literals,
    )


class HypothesisSpaceGenerator:
    def __init__(self, task: InductiveTask, args: Arguments) -> None:
        self.task = task
        self.args = args
        self.fragments = _task_fragments(task)
        if task.max_head_literals is not None and any(
            head.width > task.max_head_literals
            for head in task.language_bias_head
        ):
            raise ValueError("#modeh element count exceeds #maxhl")
        if (
            task.language_bias_aggregate_head
            and task.max_head_literals is not None
            and task.min_aggregate_head_literals > task.max_head_literals
        ):
            raise ValueError("#minhl cannot exceed #maxhl")
        _validate_invented_predicates(task, self.fragments)
        self.predicate_arg_types = _predicate_arg_types(task, self.fragments)
        self.aggregate_specs = _valid_aggregate_specs(task, self.fragments)
        self.capabilities = _hypothesis_capabilities(
            task, self.predicate_arg_types, self.aggregate_specs
        )
        self.modes = _hypothesis_modes(
            task,
            self.capabilities,
            self.predicate_arg_types,
            self.aggregate_specs,
        )
        self.modes_by_id = {mode.id: mode for mode in self.modes}
        self.head_slots = _section_capacity(
            task.max_head_literals, self.modes, "head"
        )
        self.body_slots = _section_capacity(
            task.max_body_literals, self.modes, "body"
        )
        if task.max_body_literals is None:
            self.body_slots += _condition_limit(task)
        self.max_variables = (
            task.max_variables
            if task.max_variables is not None
            else self.head_slots
            * max(
                (
                    _variable_arity(mode)
                    for mode in self.modes
                    if mode.section == "head"
                ),
                default=0,
            )
            + self.body_slots
            * max(
                (
                    _variable_arity(mode)
                    for mode in self.modes
                    if mode.section == "body"
                ),
                default=0,
            )
        )

    def generate(self) -> RuleSpace:
        facts = _facts(
            self.task,
            self.modes,
            self.predicate_arg_types,
            self.max_variables,
            self.head_slots,
            self.body_slots,
        )
        if not self.task.bias:
            facts += "\ndefault_variable_identity."
        asp_program = "\n".join((facts, HYPOTHESIS_SPACE_RULES))
        solver_arguments = ["0", *_hypothesis_space_args(self.args)]
        ctl = clingo.Control(solver_arguments, logger=wrapper_exit_callback)
        ctl.add("base", [], asp_program)
        add_program(ctl, self.task.bias)
        start = net_time()
        ctl.ground([("base", [])])
        grounding_seconds = net_time() - start
        phase = current_phase()
        add(f"{phase}.grounding", grounding_seconds)
        model_index = _model_literal_index(ctl.symbolic_atoms, self.modes_by_id)

        clauses: list[ReifiedClause] = []
        seconds = 0.0
        collect_metrics = metric_enabled("clingo")
        start = net_time()
        with ctl.solve(yield_=True) as handle:
            seconds += net_time() - start
            iterator = iter(handle)
            while True:
                start = net_time()
                try:
                    model = next(iterator)
                except StopIteration:
                    seconds += net_time() - start
                    break
                seconds += net_time() - start
                clause = _clause_from_model(model, model_index)
                if _theta_reduced(clause, self.modes_by_id):
                    clauses.append(clause)
            start = net_time()
        seconds += net_time() - start
        representatives: dict[
            ArithmeticSystemKey,
            tuple[str, ReifiedClause],
        ] = {}
        for clause in clauses:
            canonical = canonical_arithmetic_clause(
                clause,
                self.modes_by_id,
                self.max_variables,
            )
            if canonical is None:
                continue
            current = representatives.get(canonical.key)
            if current is None:
                representatives[canonical.key] = (
                    canonical.render(self.modes_by_id),
                    clause,
                )
            elif len(clause.body) > len(current[1].body):
                continue
            elif all(
                isinstance(relation, LinearConstraint)
                for system in canonical.systems
                for relation in system.relations
            ):
                if len(clause.body) < len(current[1].body):
                    representatives[canonical.key] = current[0], clause
            else:
                rendered = canonical.render(self.modes_by_id)
                if (len(clause.body), rendered) < (
                    len(current[1].body),
                    current[0],
                ):
                    representatives[canonical.key] = rendered, clause
        add(f"{phase}.solving", seconds)
        if collect_metrics:
            with instrumentation():
                stats = ctl.statistics
                models = clingo_stat(stats, "summary", "models", "enumerated")
                grounded = ground_stats(stats)
                clingo_arguments = " ".join(solver_arguments)
                record_metric(
                    "clingo",
                    {
                        "operation_category": "grounding",
                        "phase_context": phase,
                        "seconds": grounding_seconds,
                        "program_size": 1,
                        "program_chars": len(asp_program)
                        + sum(len(str(statement)) for statement in self.task.bias),
                        "stats_atoms": grounded["atoms"],
                        "stats_rules": grounded["rules"],
                        "clingo_arguments": clingo_arguments,
                    },
                )
                record_metric(
                    "clingo",
                    {
                        "operation_category": "solving",
                        "phase_context": phase,
                        "seconds": seconds,
                        "models": models,
                        "program_size": 1,
                        "has_numeric_evidence": self.capabilities.has_numeric_evidence,
                        "allow_numeric_comparison": self.capabilities.allow_numeric_comparison,
                        "allow_equality_comparison": self.capabilities.allow_equality_comparison,
                        "allow_arithmetic": self.capabilities.allow_arithmetic,
                        "allow_aggregates": self.capabilities.allow_aggregates,
                        "allow_recursion": self.capabilities.allow_recursion,
                        "clingo_arguments": clingo_arguments,
                        "stats_choices": clingo_stat(
                            stats, "solving", "solvers", "choices"
                        ),
                        "stats_conflicts": clingo_stat(
                            stats, "solving", "solvers", "conflicts"
                        ),
                    },
                )

        entries = [
            _rule_entry_from_clause(
                rendered,
                clause,
                self.modes_by_id,
            )
            for rendered, clause in sorted(
                representatives.values(), key=lambda representative: representative[0]
            )
        ]
        return RuleSpace(entries)


@profile_phase("hypothesis_space")
def build_hypothesis_space(task: InductiveTask, arguments: Arguments) -> RuleSpace:
    rule_space = HypothesisSpaceGenerator(task, arguments).generate()
    if task.metarule_programs:
        entries = list(rule_space.entries)
        known_rules = {entry.text for entry in entries}
        bundle_offset = (
            max(
                (entry.bundle for entry in entries if entry.bundle is not None),
                default=-1,
            )
            + 1
        )
        for bundle, rules in enumerate(task.metarule_programs, bundle_offset):
            for rule_ast in rules:
                rule = str(rule_ast)
                if rule in known_rules:
                    raise ValueError(
                        f"metarule rule duplicates another hypothesis rule: {rule}"
                    )
                known_rules.add(rule)
                heads, deps, body_literals = clause_predicates(rule_ast)
                head_literals = _rule_head_width(rule_ast)
                if (
                    task.max_head_literals is not None
                    and head_literals > task.max_head_literals
                ):
                    raise ValueError(f"metarule exceeds #maxhl: {rule}")
                if (
                    task.max_body_literals is not None
                    and body_literals > task.max_body_literals
                ):
                    raise ValueError(f"metarule exceeds #maxbl: {rule}")
                variables = _term_variables(rule_ast)
                if (
                    task.max_variables is not None
                    and len(variables) > task.max_variables
                ):
                    raise ValueError(f"metarule exceeds #maxv: {rule}")
                entries.append(
                    RuleEntry(rule, rule_ast, heads, deps, body_literals, bundle)
                )
        rule_space = RuleSpace.from_entries(entries)
    if metric_enabled("candidate"):
        with instrumentation():
            record_metric(
                "candidate",
                hypothesis_space_metrics(task, rule_space),
            )
    return rule_space


def _rule_head_width(rule: ast.AST) -> int:
    head = rule.head
    if (
        head.ast_type == ast.ASTType.Literal
        and head.atom.ast_type == ast.ASTType.BooleanConstant
    ):
        return 0
    if head.ast_type in {ast.ASTType.Literal, ast.ASTType.ConditionalLiteral}:
        return 1
    if head.ast_type in {ast.ASTType.Disjunction, ast.ASTType.Aggregate}:
        return len(head.elements)
    return 0


def hypothesis_space_metrics(
    task: InductiveTask, rule_space: RuleSpace
) -> dict[str, object]:
    invented = set(task.invented_predicates)
    return {
        "metric": "hypothesis_space",
        "clauses": len(rule_space),
        "invented_predicates": len(invented),
        "invented_definition_clauses": sum(
            bool(entry.heads & invented) for entry in rule_space.entries
        ),
        "invented_consumer_clauses": sum(
            bool(entry.deps & invented) for entry in rule_space.entries
        ),
    }


def _numeric_domain_values(task: InductiveTask) -> set[int]:
    fragments = [*render_program(task.background)]
    for example in [*task.positive_examples, *task.negative_examples]:
        fragments.extend(
            [example.included_text, example.excluded_text, example.context_text]
        )
    constants = _numeric_constants(fragments)
    values = set(constants.values())
    for fragment in fragments:
        for start, end in re.findall(r"(-?\d+)\.\.([A-Za-z_]\w*|-?\d+)", fragment):
            if end.lstrip("-").isdigit():
                end_value = int(end)
            elif end in constants:
                end_value = constants[end]
            else:
                continue
            start_value = int(start)
            if abs(end_value - start_value) <= 10000:
                step = 1 if start_value <= end_value else -1
                values.update(range(start_value, end_value + step, step))
        values.update(
            int(value) for value in re.findall(r"(?<![\w-])-?\d+(?![\w])", fragment)
        )
    return values


def _numeric_constants(fragments: list[str]) -> dict[str, int]:
    constants: dict[str, int] = {}
    for fragment in fragments:
        for name, value in re.findall(
            r"#const\s+([A-Za-z_]\w*)\s*=\s*(-?\d+)\s*\.", fragment
        ):
            constants[name] = int(value)
    return constants


def _closed_world_extensions(
    fragments: list[str],
) -> dict[Predicate, set[tuple[str, ...]]]:
    extensions: dict[Predicate, set[tuple[str, ...]]] = {}
    constants = _numeric_constants(fragments)
    for fragment in fragments:
        for name, arguments, _negative in fragment_atoms(fragment):
            if any(_has_variable(argument) for argument in arguments):
                continue
            key = (name, len(arguments))
            for values in _expand_ground_arguments(arguments, constants):
                extensions.setdefault(key, set()).add(values)
    _derive_closed_world_extensions(fragments, extensions)
    return extensions


def _derive_closed_world_extensions(
    fragments: list[str],
    extensions: dict[Predicate, set[tuple[str, ...]]],
    limit: int = 10000,
) -> None:
    changed = True
    while changed:
        changed = False
        for fragment in fragments:
            derived = _derive_closed_world_rule(fragment, extensions, limit)
            for predicate, tuples in derived.items():
                current = extensions.setdefault(predicate, set())
                if len(current) + len(tuples - current) > limit:
                    continue
                before = len(current)
                current.update(tuples)
                changed |= len(current) != before


def _derive_closed_world_rule(
    fragment: str,
    extensions: dict[Predicate, set[tuple[str, ...]]],
    limit: int,
) -> dict[Predicate, set[tuple[str, ...]]]:
    text = fragment.strip()
    if not text.endswith(".") or ":-" not in text or text.startswith("#"):
        return {}
    head_text, body_text = text[:-1].split(":-", 1)
    head = _simple_atom(head_text.strip())
    if head is None or any(not _is_variable(argument) for argument in head[1]):
        return {}
    positive: list[tuple[str, tuple[str, ...]]] = []
    negative: list[tuple[str, tuple[str, ...]]] = []
    for literal in _split_top_level(body_text):
        if literal.startswith("not "):
            atom = _simple_atom(literal[4:].strip())
            if atom is None:
                return {}
            negative.append(atom)
        else:
            atom = _simple_atom(literal)
            if atom is None:
                return {}
            positive.append(atom)
    if not positive or len(negative) > 1:
        return {}
    if negative and (negative[0][0], len(negative[0][1])) not in extensions:
        return {}
    assignments = [{}]
    for name, arguments in positive:
        tuples = extensions.get((name, len(arguments)))
        if tuples is None:
            return {}
        next_assignments = []
        for assignment in assignments:
            for values in tuples:
                merged = _merge_assignment(assignment, arguments, values)
                if merged is not None:
                    next_assignments.append(merged)
                    if len(next_assignments) > limit:
                        return {}
        assignments = next_assignments
    tuples: set[tuple[str, ...]] = set()
    for assignment in assignments:
        if negative and _negative_atom_holds(negative[0], assignment, extensions):
            continue
        try:
            tuples.add(tuple(assignment[argument] for argument in head[1]))
        except KeyError:
            return {}
    return {(head[0], len(head[1])): tuples}


def _split_top_level(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
        else:
            current.append(char)
    part = "".join(current).strip()
    if part:
        parts.append(part)
    return parts


def _simple_atom(text: str) -> tuple[str, tuple[str, ...]] | None:
    match = re.fullmatch(r"(-?[a-z][A-Za-z0-9_]*)\((.*)\)", text)
    if not match:
        return None
    return match.group(1), tuple(
        part.strip() for part in _split_top_level(match.group(2))
    )


def _merge_assignment(
    assignment: dict[str, str],
    arguments: tuple[str, ...],
    values: tuple[str, ...],
) -> dict[str, str] | None:
    merged = dict(assignment)
    for argument, value in zip(arguments, values):
        if _is_variable(argument):
            if argument in merged and merged[argument] != value:
                return None
            merged[argument] = value
        elif argument != value:
            return None
    return merged


def _negative_atom_holds(
    atom: tuple[str, tuple[str, ...]],
    assignment: dict[str, str],
    extensions: dict[Predicate, set[tuple[str, ...]]],
) -> bool:
    name, arguments = atom
    values: list[str] = []
    for argument in arguments:
        if _is_variable(argument):
            if argument not in assignment:
                return False
            values.append(assignment[argument])
        else:
            values.append(argument)
    return tuple(values) in extensions.get((name, len(arguments)), set())


def _expand_ground_arguments(
    arguments: tuple[str, ...],
    constants: dict[str, int],
    limit: int = 10000,
) -> list[tuple[str, ...]]:
    domains: list[list[str]] = []
    size = 1
    for argument in arguments:
        values = _expand_ground_argument(argument, constants)
        if values is None:
            return []
        size *= len(values)
        if size > limit:
            return []
        domains.append(values)
    return [tuple(values) for values in product(*domains)]


def _expand_ground_argument(
    argument: str, constants: dict[str, int]
) -> list[str] | None:
    text = argument.strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    match = re.fullmatch(r"(-?\d+)\.\.([A-Za-z_]\w*|-?\d+)", text)
    if not match:
        if ".." in text:
            return None
        return [argument]
    start = int(match.group(1))
    end_text = match.group(2)
    if end_text.lstrip("-").isdigit():
        end = int(end_text)
    elif end_text in constants:
        end = constants[end_text]
    else:
        return None
    step = 1 if start <= end else -1
    return [str(value) for value in range(start, end + step, step)]


def _defined_predicates(fragments: list[str]) -> set[Predicate]:
    defined: set[Predicate] = set()
    clauses = [
        fragment
        for fragment in fragments
        if fragment.strip().endswith(".") and not fragment.lstrip().startswith("#")
    ]
    for entry in RuleSpace.from_clauses(clauses).entries:
        defined.update(entry.heads)
    return defined


def _type_domains(
    fragments: list[str],
    predicate_arg_types: dict[tuple[str, int, int], str],
) -> dict[str, set[str]]:
    domains: dict[str, set[str]] = {}
    constants = _numeric_constants(fragments)
    for fragment in fragments:
        for name, arguments, _negative in fragment_atoms(fragment):
            if any(_has_variable(argument) for argument in arguments):
                continue
            arity = len(arguments)
            for values in _expand_ground_arguments(arguments, constants):
                for index, value in enumerate(values):
                    arg_type = predicate_arg_types.get(
                        (name.removeprefix("-"), arity, index), "any"
                    )
                    if arg_type != "any":
                        domains.setdefault(arg_type, set()).add(value)
    return domains


def _universal_predicates(
    extensions: dict[Predicate, set[tuple[str, ...]]],
    predicate_arg_types: dict[tuple[str, int, int], str],
    type_domains: dict[str, set[str]],
    unary_type_domains: dict[str, dict[Predicate, set[str]]],
) -> set[Predicate]:
    universal: set[Predicate] = set()
    for predicate, tuples in extensions.items():
        domains: list[set[str]] = []
        for index in range(predicate[1]):
            arg_type = predicate_arg_types.get(
                (predicate[0].removeprefix("-"), predicate[1], index), "any"
            )
            domain = type_domains.get(arg_type, set())
            explicit_domain = set().union(
                *(
                    values
                    for source, values in unary_type_domains.get(arg_type, {}).items()
                    if source != predicate
                ),
                set(),
            )
            if arg_type == "any" or not domain or explicit_domain != domain:
                break
            domains.append(domain)
        else:
            size = 1
            for domain in domains:
                size *= len(domain)
            if size <= 10000 and tuples == set(product(*domains)):
                universal.add(predicate)
    return universal


def _unary_type_domains(
    fragments: list[str],
    predicate_arg_types: dict[tuple[str, int, int], str],
) -> dict[str, dict[Predicate, set[str]]]:
    domains: dict[str, dict[Predicate, set[str]]] = {}
    constants = _numeric_constants(fragments)
    for fragment in fragments:
        for name, arguments, _negative in fragment_atoms(fragment):
            if len(arguments) != 1:
                continue
            value = arguments[0]
            if _has_variable(value):
                continue
            arg_type = predicate_arg_types.get((name.removeprefix("-"), 1, 0), "any")
            values = _expand_ground_argument(value, constants)
            if arg_type != "any" and values is not None:
                domains.setdefault(arg_type, {}).setdefault((name, 1), set()).update(
                    values
                )
    return domains


def _closed_world_properties(
    fragments: list[str],
    predicate_arg_types: dict[tuple[str, int, int], str] | None = None,
    closed_body_predicates: set[Predicate] | None = None,
) -> ClosedWorldProperties:
    extensions = _closed_world_extensions(fragments)
    symmetric: set[Predicate] = set()
    asymmetric: set[Predicate] = set()
    antisymmetric: set[Predicate] = set()
    acyclic: set[Predicate] = set()
    reflexive: set[Predicate] = set()
    strict_order: set[Predicate] = set()
    total_order: set[Predicate] = set()
    inverse: set[tuple[Predicate, Predicate]] = set()
    implies: set[tuple[Predicate, Predicate]] = set()
    equivalent: set[tuple[Predicate, Predicate]] = set()
    project_implies: set[tuple[Predicate, Predicate, tuple[int, ...]]] = set()
    disjoint_projection: set[tuple[Predicate, int, Predicate, int]] = set()
    tuple_mutex: set[tuple[Predicate, Predicate, tuple[int, ...]]] = set()
    mutex: set[tuple[Predicate, Predicate]] = set()
    complement: set[tuple[Predicate, Predicate]] = set()
    partitions: set[tuple[Predicate, ...]] = set()
    universal: set[Predicate] = set()
    empty: set[Predicate] = set()
    arg_equal: set[tuple[Predicate, int, int]] = set()
    arg_distinct: set[tuple[Predicate, int, int]] = set()
    functional: set[tuple[Predicate, int, int]] = set()
    functional_set: set[tuple[Predicate, tuple[int, ...], int]] = set()
    keys: set[tuple[Predicate, tuple[int, ...]]] = set()
    cardinality_upper: set[tuple[Predicate, int]] = set()
    transitive: set[Predicate] = set()
    tuple_universe_by_arity: dict[int, set[tuple[str, ...]]] = {}
    (
        choice_functional,
        choice_functional_set,
        choice_keys,
        choice_project_implies,
        choice_cardinality_upper,
    ) = _choice_rule_properties(fragments)
    for predicate, tuples in extensions.items():
        tuple_universe_by_arity.setdefault(predicate[1], set()).update(tuples)

    for predicate, tuples in extensions.items():
        _collect_argument_properties(predicate, tuples, arg_equal, arg_distinct)
        _collect_functional_properties(predicate, tuples, functional)
        _collect_composite_functional_properties(predicate, tuples, functional_set)
        _collect_key_properties(predicate, tuples, keys)
        if predicate[1] == 2:
            reversed_tuples = {(right, left) for left, right in tuples}
            if tuples == reversed_tuples:
                symmetric.add(predicate)
            if tuples.isdisjoint(reversed_tuples):
                asymmetric.add(predicate)
            if all(
                left == right or (right, left) not in tuples for left, right in tuples
            ):
                antisymmetric.add(predicate)
            if _is_acyclic(tuples):
                acyclic.add(predicate)
            transitive_pred = _is_transitive(tuples)
            if transitive_pred:
                transitive.add(predicate)
            if _is_reflexive(tuples):
                reflexive.add(predicate)
            if tuples and tuples.isdisjoint(reversed_tuples) and transitive_pred:
                strict_order.add(predicate)
            if _is_total_order(tuples):
                total_order.add(predicate)

    for left, right in combinations(sorted(extensions), 2):
        left_tuples = extensions[left]
        right_tuples = extensions[right]
        if left[1] == right[1]:
            if left_tuples == right_tuples:
                equivalent.add((min(left, right), max(left, right)))
            elif left_tuples <= right_tuples:
                implies.add((left, right))
            elif right_tuples <= left_tuples:
                implies.add((right, left))
            if left_tuples.isdisjoint(right_tuples):
                universe = tuple_universe_by_arity[left[1]]
                if left_tuples | right_tuples == universe:
                    complement.add((min(left, right), max(left, right)))
                else:
                    mutex.add((min(left, right), max(left, right)))
            if left[1] == 2 and left_tuples == {(b, a) for a, b in right_tuples}:
                inverse.add((min(left, right), max(left, right)))
        _collect_disjoint_projections(
            left, left_tuples, right, right_tuples, disjoint_projection
        )
        _collect_projection_implications(
            left, left_tuples, right, right_tuples, project_implies
        )
        _collect_projection_implications(
            right, right_tuples, left, left_tuples, project_implies
        )
    if closed_body_predicates:
        _collect_tuple_mutex(extensions, closed_body_predicates, tuple_mutex)
    functional.update(choice_functional)
    functional_set.update(choice_functional_set)
    keys.update(choice_keys)
    project_implies.update(choice_project_implies)
    cardinality_upper.update(choice_cardinality_upper)
    _collect_rule_defined_properties(
        fragments,
        keys,
        functional,
        functional_set,
        arg_distinct,
        symmetric,
    )
    partitions.update(_partition_properties(extensions, tuple_universe_by_arity))
    if predicate_arg_types:
        type_domains = _type_domains(fragments, predicate_arg_types)
        unary_type_domains = _unary_type_domains(fragments, predicate_arg_types)
        universal.update(
            _universal_predicates(
                extensions,
                predicate_arg_types,
                type_domains,
                unary_type_domains,
            )
        )
    if closed_body_predicates:
        empty.update(
            predicate
            for predicate in closed_body_predicates
            if predicate not in extensions
            and predicate not in _defined_predicates(fragments)
        )
    asymmetric -= acyclic | strict_order | total_order
    acyclic -= strict_order
    antisymmetric -= acyclic | strict_order | total_order
    reflexive -= total_order | universal
    transitive -= strict_order | total_order
    mutex -= complement
    arg_distinct = _without_irreflexive_subsumed_arg_distinct(
        arg_distinct,
        asymmetric | acyclic | strict_order,
    )
    mutex = _without_partition_subsumed_mutex(mutex, partitions)
    functional = _without_key_subsumed_functional(functional, keys)
    functional_set = _without_key_subsumed_functional_set(functional_set, keys)
    functional_set = _without_subsumed_functional_set(functional_set, functional)

    return ClosedWorldProperties(
        frozenset(symmetric),
        frozenset(asymmetric),
        frozenset(antisymmetric),
        frozenset(acyclic),
        frozenset(reflexive),
        frozenset(strict_order),
        frozenset(total_order),
        frozenset(inverse),
        frozenset(implies),
        frozenset(equivalent),
        frozenset(project_implies),
        frozenset(disjoint_projection),
        frozenset(tuple_mutex),
        frozenset(mutex),
        frozenset(complement),
        frozenset(partitions),
        frozenset(universal),
        frozenset(empty),
        frozenset(arg_equal),
        frozenset(arg_distinct),
        frozenset(functional),
        frozenset(functional_set),
        frozenset(keys),
        frozenset(cardinality_upper),
        frozenset(transitive),
    )


def _choice_rule_properties(
    fragments: list[str],
) -> tuple[
    set[tuple[Predicate, int, int]],
    set[tuple[Predicate, tuple[int, ...], int]],
    set[tuple[Predicate, tuple[int, ...]]],
    set[tuple[Predicate, Predicate, tuple[int, ...]]],
    set[tuple[Predicate, int]],
]:
    functional: set[tuple[Predicate, int, int]] = set()
    functional_set: set[tuple[Predicate, tuple[int, ...], int]] = set()
    keys: set[tuple[Predicate, tuple[int, ...]]] = set()
    project_implies: set[tuple[Predicate, Predicate, tuple[int, ...]]] = set()
    cardinality_upper: dict[Predicate, int] = {}

    def collect(node: ast.AST) -> None:
        if node.ast_type != ast.ASTType.Rule:
            return
        head = node.head
        if head.ast_type != ast.ASTType.Aggregate:
            return
        if not node.body and (upper := _aggregate_upper(head)) is not None:
            predicate = _choice_predicate(head.elements)
            if predicate is not None:
                cardinality_upper[predicate] = (
                    cardinality_upper.get(predicate, 0) + upper
                )
        predicate = _choice_predicate(head.elements)
        if predicate is not None:
            project_implies.update(
                _choice_project_implies(predicate, head.elements, node.body)
            )
        if not _aggregate_upper_at_most_one(head):
            return
        result = _choice_key(node.body, head.elements)
        if result is None:
            return
        predicate, inputs, outputs = result
        keys.add((predicate, inputs))
        for output in outputs:
            if len(inputs) == 1:
                functional.add((predicate, inputs[0], output))
            else:
                functional_set.add((predicate, inputs, output))

    for fragment in fragments:
        if fragment.lstrip().startswith("#"):
            continue
        source = fragment if fragment.strip().endswith(".") else f"{fragment}."
        try:
            ast.parse_string(source, collect)
        except RuntimeError:
            continue
    return (
        functional,
        functional_set,
        keys,
        project_implies,
        set(cardinality_upper.items()),
    )


def _choice_predicate(elements: list[ast.AST]) -> Predicate | None:
    predicates: set[Predicate] = set()
    for element in elements:
        atom = _positive_symbolic_atom(element.literal)
        if atom is None:
            return None
        predicates.add((atom[0], len(atom[1])))
    return next(iter(predicates)) if len(predicates) == 1 else None


def _aggregate_upper_at_most_one(head: ast.AST) -> bool:
    return _aggregate_upper(head) == 1


def _aggregate_upper(head: ast.AST) -> int | None:
    guard = head.right_guard
    if guard is None:
        return None
    return _numeric_term_value(guard.term)


def _numeric_term_value(term: ast.AST) -> int | None:
    text = str(term)
    return int(text) if re.fullmatch(r"-?\d+", text) else None


def _choice_key(
    body: list[ast.AST],
    elements: list[ast.AST],
) -> tuple[Predicate, tuple[int, ...], tuple[int, ...]] | None:
    atoms: list[tuple[str, tuple[ast.AST, ...]]] = []
    for element in elements:
        atom = _positive_symbolic_atom(element.literal)
        if atom is None:
            return None
        atoms.append(atom)
    if not atoms:
        return None
    name = atoms[0][0]
    arity = len(atoms[0][1])
    if any(
        atom_name != name or len(arguments) != arity for atom_name, arguments in atoms
    ):
        return None

    body_vars = set().union(*(_term_variables(literal) for literal in body), set())
    input_args: list[int] = []
    output_args: list[int] = []
    for index in range(arity):
        terms = [arguments[index] for _, arguments in atoms]
        text = [_term_text(term) for term in terms]
        variables = set().union(*(_term_variables(term) for term in terms), set())
        if len(set(text)) == 1 and variables <= body_vars:
            input_args.append(index)
        else:
            output_args.append(index)

    if not input_args or not output_args:
        return None
    return (name, arity), tuple(input_args), tuple(output_args)


def _choice_project_implies(
    predicate: Predicate,
    elements: list[ast.AST],
    body: list[ast.AST],
) -> set[tuple[Predicate, Predicate, tuple[int, ...]]]:
    result: set[tuple[Predicate, Predicate, tuple[int, ...]]] = set()
    element_vars: set[str] = set()
    for element in elements:
        atom = _positive_symbolic_atom(element.literal)
        if atom is None:
            continue
        for argument in atom[1]:
            element_vars.update(_term_variables(argument))
        for condition in element.condition:
            condition_atom = _positive_symbolic_atom(condition)
            if condition_atom is not None:
                _collect_atom_projection(predicate, atom[1], condition_atom, result)
    for literal in body:
        body_atom = _positive_symbolic_atom(literal)
        if body_atom is not None and _term_variables(literal) <= element_vars:
            continue
        if body_atom is not None:
            atom = _positive_symbolic_atom(elements[0].literal)
            if atom is not None:
                _collect_atom_projection(predicate, atom[1], body_atom, result)
    return result


def _collect_atom_projection(
    source: Predicate,
    source_args: tuple[ast.AST, ...],
    target: tuple[str, tuple[ast.AST, ...]],
    result: set[tuple[Predicate, Predicate, tuple[int, ...]]],
) -> None:
    projection: list[int] = []
    for target_arg in target[1]:
        target_text = _term_text(target_arg)
        for index, source_arg in enumerate(source_args):
            if _term_text(source_arg) == target_text:
                projection.append(index)
                break
        else:
            return
    result.add((source, (target[0], len(target[1])), tuple(projection)))


def _collect_rule_defined_properties(
    fragments: list[str],
    keys: set[tuple[Predicate, tuple[int, ...]]],
    functional: set[tuple[Predicate, int, int]],
    functional_set: set[tuple[Predicate, tuple[int, ...], int]],
    arg_distinct: set[tuple[Predicate, int, int]],
    symmetric: set[Predicate],
) -> None:
    key_by_predicate = _key_sets_by_predicate(keys)
    rules_by_head: dict[Predicate, list[ast.AST]] = {}

    def collect(node: ast.AST) -> None:
        if node.ast_type != ast.ASTType.Rule:
            return
        head = _positive_symbolic_atom(node.head)
        if head is None:
            return
        rules_by_head.setdefault((head[0], len(head[1])), []).append(node)

    for fragment in fragments:
        if fragment.lstrip().startswith("#"):
            continue
        try:
            ast.parse_string(
                fragment if fragment.strip().endswith(".") else f"{fragment}.", collect
            )
        except RuntimeError:
            continue

    for rules in rules_by_head.values():
        if len(rules) != 1:
            continue
        node = rules[0]
        head = _positive_symbolic_atom(node.head)
        if head is None:
            continue
        body_atoms = [
            atom for literal in node.body if (atom := _positive_symbolic_atom(literal))
        ]
        equalities = [_square_equality(literal) for literal in node.body]
        equalities = [equality for equality in equalities if equality is not None]
        if not equalities:
            continue
        for body_atom in body_atoms:
            for key in key_by_predicate.get((body_atom[0], len(body_atom[1])), ()):
                _propagate_key_through_rule(
                    head, body_atom, key, equalities, functional, functional_set, keys
                )

    for predicate, rules in rules_by_head.items():
        if predicate[1] == 2 and all(_rule_head_args_distinct(rule) for rule in rules):
            arg_distinct.add((predicate, 0, 1))
        if predicate[1] == 2 and all(_rule_head_args_symmetric(rule) for rule in rules):
            symmetric.add(predicate)


def _rule_head_args_distinct(node: ast.AST) -> bool:
    head = _positive_symbolic_atom(node.head)
    if head is None or len(head[1]) != 2:
        return False
    inequalities = {
        inequality
        for literal in node.body
        if (inequality := _inequality_terms(literal)) is not None
    }
    if not inequalities:
        return False
    left = _term_text(head[1][0])
    right = _term_text(head[1][1])
    return _terms_known_distinct(left, right, inequalities)


def _inequality_terms(literal: ast.AST) -> tuple[str, str] | None:
    match = re.fullmatch(r"(.+)!=(.+)", _term_text(literal))
    if not match:
        return None
    return match.group(1), match.group(2)


def _terms_known_distinct(
    left: str,
    right: str,
    inequalities: set[tuple[str, str]],
) -> bool:
    if (left, right) in inequalities or (right, left) in inequalities:
        return True
    left_parts = _tuple_parts(left)
    right_parts = _tuple_parts(right)
    return (
        left_parts is not None
        and right_parts is not None
        and len(left_parts) == len(right_parts)
        and any(
            _terms_known_distinct(a, b, inequalities)
            for a, b in zip(left_parts, right_parts)
        )
    )


def _tuple_parts(text: str) -> list[str] | None:
    if not text.startswith("(") or not text.endswith(")"):
        return None
    parts = _split_top_level(text[1:-1])
    return parts if len(parts) > 1 else None


def _rule_head_args_symmetric(node: ast.AST) -> bool:
    head = _positive_symbolic_atom(node.head)
    if head is None or len(head[1]) != 2:
        return False
    mapping = _term_pair_mapping(_term_text(head[1][0]), _term_text(head[1][1]))
    if mapping is None:
        return False
    body = sorted(_canonical_literal_text(_term_text(literal)) for literal in node.body)
    swapped = sorted(
        _canonical_literal_text(_substitute_variables(_term_text(literal), mapping))
        for literal in node.body
    )
    return body == swapped


def _term_pair_mapping(left: str, right: str) -> dict[str, str] | None:
    if left == right:
        return {}
    if _is_variable(left) and _is_variable(right):
        return {left: right, right: left}
    left_parts = _tuple_parts(left)
    right_parts = _tuple_parts(right)
    if left_parts is None or right_parts is None or len(left_parts) != len(right_parts):
        return None
    mapping: dict[str, str] = {}
    for left_part, right_part in zip(left_parts, right_parts):
        part_mapping = _term_pair_mapping(left_part, right_part)
        if part_mapping is None:
            return None
        for source, target in part_mapping.items():
            if source in mapping and mapping[source] != target:
                return None
            mapping[source] = target
    return mapping


def _substitute_variables(text: str, mapping: dict[str, str]) -> str:
    return re.sub(
        r"\b[A-Z]\w*\b", lambda match: mapping.get(match.group(0), match.group(0)), text
    )


def _canonical_literal_text(text: str) -> str:
    match = re.fullmatch(r"(.+)!=(.+)", text)
    if match:
        return "!=".join(sorted((match.group(1), match.group(2))))
    return text


def _square_equality(literal: ast.AST) -> tuple[str, str] | None:
    text = _term_text(literal)
    match = re.fullmatch(r"([A-Z]\w*)=\(?([A-Z]\w*)\*\2\)?", text)
    if match:
        return match.group(1), match.group(2)
    return None


def _propagate_key_through_rule(
    head: tuple[str, tuple[ast.AST, ...]],
    body_atom: tuple[str, tuple[ast.AST, ...]],
    body_key: set[int],
    equalities: list[tuple[str, str]],
    functional: set[tuple[Predicate, int, int]],
    functional_set: set[tuple[Predicate, tuple[int, ...], int]],
    keys: set[tuple[Predicate, tuple[int, ...]]],
) -> None:
    head_args = [_term_text(argument) for argument in head[1]]
    body_args = [_term_text(argument) for argument in body_atom[1]]
    head_predicate = (head[0], len(head[1]))
    determinant_vars = {body_args[arg] for arg in body_key}
    determinant_vars |= {
        square for square, root in equalities if root in determinant_vars
    }
    determinant_positions = tuple(
        index
        for index, argument in enumerate(head_args)
        if argument in determinant_vars
    )
    if not determinant_positions:
        return
    output_positions = tuple(
        index
        for index, argument in enumerate(head_args)
        if argument not in determinant_vars
    )
    if not output_positions:
        return
    keys.add((head_predicate, determinant_positions))
    for output in output_positions:
        if len(determinant_positions) == 1:
            functional.add((head_predicate, determinant_positions[0], output))
        else:
            functional_set.add((head_predicate, determinant_positions, output))


def _positive_symbolic_atom(literal: ast.AST) -> tuple[str, tuple[ast.AST, ...]] | None:
    if literal.ast_type != ast.ASTType.Literal or literal.sign != ast.Sign.NoSign:
        return None
    atom = literal.atom
    if atom.ast_type != ast.ASTType.SymbolicAtom:
        return None
    symbol = atom.symbol
    strong = False
    if symbol.ast_type == ast.ASTType.UnaryOperation:
        if symbol.operator_type != ast.UnaryOperator.Minus:
            return None
        strong = True
        symbol = symbol.argument
    if symbol.ast_type != ast.ASTType.Function or not symbol.name:
        return None
    name = f"-{symbol.name}" if strong else str(symbol.name)
    return name, tuple(symbol.arguments)


def _term_text(term: ast.AST) -> str:
    return str(term).replace(" ", "")


def _term_variables(node: ast.AST) -> set[str]:
    variables: set[str] = set()
    if node.ast_type == ast.ASTType.Variable:
        variables.add(str(node.name))
        return variables
    for key in node.child_keys:
        child = getattr(node, key)
        if isinstance(child, ast.AST):
            variables.update(_term_variables(child))
        elif isinstance(child, list) or child.__class__.__name__ == "ASTSequence":
            for item in child:
                if isinstance(item, ast.AST):
                    variables.update(_term_variables(item))
    return variables


def _collect_argument_properties(
    predicate: Predicate,
    tuples: set[tuple[str, ...]],
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
    tuples: set[tuple[str, ...]],
    functional: set[tuple[Predicate, int, int]],
) -> None:
    for input_arg in range(predicate[1]):
        if len(tuples) < 2:
            continue
        for output_arg in range(predicate[1]):
            if input_arg == output_arg:
                continue
            outputs: dict[str, str] = {}
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
    tuples: set[tuple[str, ...]],
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
                outputs: dict[tuple[str, ...], str] = {}
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
    tuples: set[tuple[str, ...]],
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
    left_tuples: set[tuple[str, ...]],
    right: Predicate,
    right_tuples: set[tuple[str, ...]],
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
    extensions: dict[Predicate, set[tuple[str, ...]]],
    tuple_universe_by_arity: dict[int, set[tuple[str, ...]]],
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
                covered: set[tuple[str, ...]] = set()
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
    extensions: dict[Predicate, set[tuple[str, ...]]],
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
    source_tuples: set[tuple[str, ...]],
    target: Predicate,
    target_tuples: set[tuple[str, ...]],
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


def _is_transitive(tuples: set[tuple[str, ...]] | set[tuple[str, str]]) -> bool:
    if len(tuples) < 3:
        return False
    for left, middle in tuples:
        for other_middle, right in tuples:
            if middle == other_middle and (left, right) not in tuples:
                return False
    return True


def _is_reflexive(tuples: set[tuple[str, ...]]) -> bool:
    domain = {value for row in tuples for value in row}
    return bool(domain) and all((value, value) in tuples for value in domain)


def _is_total_order(tuples: set[tuple[str, ...]]) -> bool:
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


def _is_acyclic(tuples: set[tuple[str, ...]]) -> bool:
    graph: dict[str, set[str]] = {}
    for left, right in tuples:
        graph.setdefault(left, set()).add(right)
        graph.setdefault(right, set())
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
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


def _recursive_predicates(task: InductiveTask) -> set[Predicate]:
    head_predicates = {atom.signature for atom in _head_atoms(task)}
    return {
        literal.atom.signature
        for md in (*task.language_bias_body, *task.language_bias_condition)
        for literal in _mode_atom_literals(md)
        if not literal.default_negated and literal.atom.signature in head_predicates
    }


def _head_atoms(task: InductiveTask) -> tuple[AtomTemplate, ...]:
    return tuple(
        atom
        for declaration in task.language_bias_head
        for atom in declaration.template.elements
    ) + tuple(
        mode.literal.atom
        for mode in (
            *task.language_bias_aggregate_head,
            *task.language_bias_disjunctive_head,
        )
        if isinstance(mode.literal, AtomLiteral)
    )


def _mode_atom_literals(mode: ModeDeclaration) -> tuple[AtomLiteral, ...]:
    if isinstance(mode.literal, AtomLiteral):
        return (mode.literal,)
    if isinstance(mode.literal, ConditionalLiteral):
        return tuple(
            literal
            for literal in (mode.literal.conclusion, *mode.literal.conditions)
            if isinstance(literal, AtomLiteral)
        )
    return ()


def _validate_invented_predicates(task: InductiveTask, fragments: list[str]) -> None:
    invented = set(task.invented_predicates)
    if len(invented) != len(task.invented_predicates):
        raise ValueError("duplicate invented predicate")
    heads = {atom.signature for atom in _head_atoms(task)}
    positive_bodies = {
        literal.atom.signature
        for mode in task.language_bias_body
        for literal in _mode_atom_literals(mode)[:1]
        if not literal.default_negated
    }
    missing = invented - (heads & positive_bodies)
    if missing:
        raise ValueError(
            f"invented predicates require generated head and positive body modes: {sorted(missing)}"
        )
    observed = invented & _observed_predicates(fragments)
    if observed:
        raise ValueError(
            f"invented predicates must not be observed: {sorted(observed)}"
        )


def _hypothesis_capabilities(
    task: InductiveTask,
    predicate_arg_types: dict[tuple[str, int, int], str],
    aggregate_specs: list[AggregateDeclaration],
) -> HypothesisCapabilities:
    numeric_evidence = any(
        arg_type == "numeric" for arg_type in predicate_arg_types.values()
    )
    comparison_operators = {
        mode.operator
        for mode in task.arithmetic_modes
        if isinstance(mode, OperatorDeclaration)
        and mode.operator in {"eq", "neq", "lt", "leq", "gt", "geq"}
    }
    equality_comparison = bool({"eq", "neq"} & comparison_operators)
    numeric_comparison = numeric_evidence and bool(
        comparison_operators & {"lt", "leq", "gt", "geq"}
    )
    return HypothesisCapabilities(
        has_numeric_evidence=numeric_evidence,
        allow_numeric_comparison=numeric_comparison,
        allow_equality_comparison=equality_comparison,
        allow_arithmetic=numeric_evidence and bool(task.arithmetic_modes),
        allow_aggregates=bool(aggregate_specs),
        allow_recursion=bool(_recursive_predicates(task)),
    )


def _available_predicates(
    task: InductiveTask, fragments: list[str]
) -> set[tuple[str, int]]:
    predicates = {atom.signature for atom in _head_atoms(task)} | {
        literal.atom.signature
        for mode in (*task.language_bias_body, *task.language_bias_condition)
        for literal in _mode_atom_literals(mode)
    }
    for fragment in fragments:
        for name, arguments, _negative in fragment_atoms(fragment):
            predicates.add((name, len(arguments)))
    return predicates


def _observed_predicates(fragments: list[str]) -> set[Predicate]:
    predicates: set[Predicate] = set()
    for fragment in fragments:
        for name, arguments, _negative in fragment_atoms(fragment):
            predicates.add((name, len(arguments)))
    return predicates


def _predicate_arg_types(
    task: InductiveTask, fragments: list[str]
) -> dict[tuple[str, int, int], str]:
    declared_atoms = [
        *_head_atoms(task),
        *(
            literal.atom
            for mode in (*task.language_bias_body, *task.language_bias_condition)
            for literal in _mode_atom_literals(mode)
        ),
    ]
    positions = {
        (*atom.unsigned_signature, arg)
        for atom in declared_atoms
        for arg in range(len(atom.terms))
    }
    constants_by_position: dict[tuple[str, int, int], set[str]] = {
        position: set() for position in positions
    }
    variable_position_groups: list[list[tuple[str, int, int]]] = []
    for fragment in fragments:
        positions_by_variable: dict[str, list[tuple[str, int, int]]] = {}
        for name, arguments, _negative in fragment_atoms(fragment):
            name = name.removeprefix("-")
            arity = len(arguments)
            for index, value in enumerate(arguments):
                position = (name, arity, index)
                positions.add(position)
                if _is_variable(value):
                    positions_by_variable.setdefault(value, []).append(position)
                elif _has_variable(value):
                    continue
                else:
                    constants_by_position.setdefault(position, set()).add(value)
        variable_position_groups.extend(
            group for group in positions_by_variable.values() if len(group) > 1
        )

    parent = {position: position for position in positions}

    def find(position: tuple[str, int, int]) -> tuple[str, int, int]:
        while parent[position] != position:
            parent[position] = parent[parent[position]]
            position = parent[position]
        return position

    def union(left: tuple[str, int, int], right: tuple[str, int, int]) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for shared_positions in variable_position_groups:
        for other in shared_positions[1:]:
            union(shared_positions[0], other)

    constants_by_root: dict[tuple[str, int, int], set[str]] = {}
    for position in positions:
        root = find(position)
        constants_by_root.setdefault(root, set()).update(
            constants_by_position.get(position, set())
        )

    declared_types_by_root: dict[tuple[str, int, int], set[str]] = {}
    for atom in declared_atoms:
        for index, argument in enumerate(atom.terms):
            if argument.kind not in {"variable", "constant"}:
                continue
            position = (*atom.unsigned_signature, index)
            declared_types_by_root.setdefault(find(position), set()).add(argument.type)
    type_by_root: dict[tuple[str, int, int], str] = {}
    next_type = 0
    for root, constants in constants_by_root.items():
        if len(declared_types_by_root.get(root, ())) == 1:
            type_by_root[root] = next(iter(declared_types_by_root[root]))
        elif constants and all(_is_numeric_constant(value) for value in constants):
            type_by_root[root] = "numeric"
        elif constants:
            type_by_root[root] = f"type_{next_type}"
            next_type += 1
        else:
            type_by_root[root] = "any"

    return {position: type_by_root[find(position)] for position in positions}


def _is_numeric_constant(value: str) -> bool:
    value = value.strip("()")
    bound = r"[-+]?\d+|[A-Za-z_]\w*"
    return bool(re.fullmatch(rf"[-+]?\d+(?:\.\.({bound}))?", value))


def _is_variable(value: str) -> bool:
    return bool(re.fullmatch(r"_|[A-Z]\w*", value))


def _has_variable(value: str) -> bool:
    return bool(re.search(r"\b[A-Z]\w*\b|_", value))


def _task_fragments(task: InductiveTask) -> list[str]:
    fragments = [
        line
        for line in render_program(task.background)
        if line.strip() and not line.lstrip().startswith("%")
    ]
    for example in [*task.positive_examples, *task.negative_examples]:
        fragments.extend(
            [example.included_text, example.excluded_text, example.context_text]
        )
    return [fragment for fragment in fragments if fragment.strip()]


def _closed_world_fragments(task: InductiveTask) -> list[str]:
    fragments = [
        line
        for line in render_program(task.background)
        if line.strip() and not line.lstrip().startswith("%")
    ]
    for example in task.positive_examples:
        fragments.append(example.context_text)
    for example in task.negative_examples:
        fragments.append(example.context_text)
    return [fragment for fragment in fragments if fragment.strip()]


def _valid_aggregate_specs(
    task: InductiveTask,
    fragments: list[str] | None = None,
) -> list[AggregateDeclaration]:
    if not task.aggregate_modes:
        return []
    available = _available_predicates(task, fragments or _task_fragments(task))
    valid = []
    for spec in task.aggregate_modes:
        if all(atom in available for atom in spec.atoms):
            valid.append(spec)
    return valid


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


def _hypothesis_modes(
    task: InductiveTask,
    capabilities: HypothesisCapabilities,
    predicate_arg_types: dict[tuple[str, int, int], str],
    aggregate_specs: list[AggregateDeclaration],
) -> list[HypothesisMode]:
    modes: list[HypothesisMode] = []
    next_id = 0

    def add(mode: HypothesisMode) -> None:
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
                        HypothesisMode(
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
                    HypothesisMode(
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
                HypothesisMode(
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
                HypothesisMode(
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
                HypothesisMode(
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
                    HypothesisMode(
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
                HypothesisMode(
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


def _variable_arity(mode: HypothesisMode) -> int:
    return len(mode.bindings)


def _binding_positions(mode: HypothesisMode) -> tuple[int, ...]:
    if isinstance(
        mode.literal, ConditionalLiteral | ComparisonLiteral | ArithmeticLiteral
    ) or (
        isinstance(mode.literal, AtomLiteral)
        and any(term.kind in {"function", "tuple"} for term in mode.literal.atom.terms)
    ):
        return tuple(range(len(mode.bindings)))
    return tuple(binding.path[0] for binding in mode.bindings)


def _section_capacity(
    limit: int | None, modes: list[HypothesisMode], section: str
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


def _facts(
    task: InductiveTask,
    modes: list[HypothesisMode],
    predicate_arg_types: dict[tuple[str, int, int], str],
    max_variables: int,
    max_head_literals: int,
    max_body_literals: int,
) -> str:
    fragments = _closed_world_fragments(task)
    properties = _closed_world_properties(
        fragments,
        predicate_arg_types,
        _closed_body_predicates(task),
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


def _predicate_ids(modes: list[HypothesisMode]) -> dict[Predicate, int]:
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


def _model_literal_index(
    atoms: clingo.SymbolicAtoms,
    modes: dict[int, HypothesisMode],
) -> tuple[_ModelSlot, ...]:
    selected: dict[tuple[str, int], list[tuple[int, int]]] = {}
    variables: dict[tuple[str, int, int], list[tuple[int, int]]] = {}
    for atom in atoms.by_signature("selected", 3):
        section, slot, mode = atom.symbol.arguments
        selected.setdefault((section.name, slot.number), []).append(
            (mode.number, atom.literal)
        )
    for atom in atoms.by_signature("var_at", 4):
        section, slot, argument, variable = atom.symbol.arguments
        variables.setdefault((section.name, slot.number, argument.number), []).append(
            (variable.number, atom.literal)
        )
    return tuple(
        (
            section,
            slot,
            tuple(
                (
                    mode_id,
                    _binding_positions(modes[mode_id]),
                    literal,
                )
                for mode_id, literal in sorted(mode_choices)
            ),
            tuple(
                tuple(sorted(variables.get((section, slot, argument), ())))
                for argument in range(
                    max(
                        max(_binding_positions(modes[mode_id]), default=-1) + 1
                        for mode_id, _literal in mode_choices
                    )
                )
            ),
        )
        for (section, slot), mode_choices in sorted(selected.items())
    )


def _clause_from_model(
    model: clingo.Model,
    model_index: tuple[_ModelSlot, ...],
) -> ReifiedClause:
    is_true = model.is_true
    head: list[ReifiedLiteral] = []
    body: list[ReifiedLiteral] = []
    current_section = ""
    minimum_mode = -1
    section_empty = False
    for section, slot, mode_choices, argument_choices in model_index:
        if section != current_section:
            current_section = section
            minimum_mode = -1
            section_empty = False
        if section_empty:
            continue
        mode_id = None
        variable_positions: tuple[int, ...] = ()
        for candidate_mode, candidate_positions, program_literal in mode_choices:
            if candidate_mode < minimum_mode:
                continue
            if is_true(program_literal):
                mode_id = candidate_mode
                variable_positions = candidate_positions
                break
        if mode_id is None:
            section_empty = True
            continue
        minimum_mode = mode_id
        variables: list[int] = []
        for argument in variable_positions:
            choices = argument_choices[argument]
            for variable, program_literal in choices:
                if is_true(program_literal):
                    variables.append(variable)
                    break
            else:
                raise RuntimeError("selected literal argument has no variable")
        literal = ReifiedLiteral(section, slot, mode_id, tuple(variables))
        (head if section == "head" else body).append(literal)
    return ReifiedClause(head=tuple(head), body=tuple(body))


def _theta_reduced(
    clause: ReifiedClause,
    modes: dict[int, HypothesisMode],
) -> bool:
    """Reject normal clauses θ-equivalent to one of their proper subclauses."""
    literals = (*clause.head, *clause.body)
    if any(
        not isinstance(modes[literal.mode_id].literal, AtomLiteral)
        for literal in literals
    ):
        return True
    signatures = tuple((literal.section, literal.mode_id) for literal in literals)
    repeated = {
        signature for signature in signatures if signatures.count(signature) > 1
    }
    if not repeated:
        return True
    return not any(
        _theta_subsumes(literals, literals[:index] + literals[index + 1 :])
        for index in range(len(literals))
        if signatures[index] in repeated
    )


def _theta_subsumes(
    source: tuple[ReifiedLiteral, ...],
    target: tuple[ReifiedLiteral, ...],
) -> bool:
    candidates = {
        literal: tuple(
            candidate
            for candidate in target
            if (candidate.section, candidate.mode_id)
            == (literal.section, literal.mode_id)
        )
        for literal in source
    }
    if any(not matches for matches in candidates.values()):
        return False
    ordered = sorted(source, key=lambda literal: len(candidates[literal]))

    def match(index: int, substitution: dict[int, int]) -> bool:
        if index == len(ordered):
            return True
        literal = ordered[index]
        for candidate in candidates[literal]:
            extended = substitution.copy()
            if all(
                extended.setdefault(variable, target_variable) == target_variable
                for variable, target_variable in zip(
                    literal.variables, candidate.variables, strict=True
                )
            ) and match(index + 1, extended):
                return True
        return False

    return match(0, {})


def _hypothesis_space_args(args: Arguments) -> list[str]:
    value = args.hypothesis_space.get("clingo_arguments", [])
    if isinstance(value, list):
        return [str(item) for item in value]
    raise ValueError("hypothesis_space.clingo_arguments must be a list")
