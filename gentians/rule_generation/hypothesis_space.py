from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations, permutations, product
from pathlib import Path
import re
import time

import clingo
from clingo import ast

from ..arguments import Arguments
from ..asp.callbacks import wrapper_exit_callback
from ..asp.stats import ground_stats
from ..timing import (
    add,
    current_phase,
    instrumentation,
    metric_enabled,
    profile_phase,
    record_metric,
)
from .parser import fragment_atoms
from .program import AggregateDeclaration, Program
from .rule_space import Predicate, RuleEntry, RuleSpace


HYPOTHESIS_SPACE_RULE_MODULES = (
    "core/slots.lp",
    "core/limits.lp",
    "core/constraints.lp",
    "core/recall.lp",
    "core/arguments.lp",
    "core/literals.lp",
    "core/tuple_helpers.lp",
    "aggregates/roles.lp",
    "safety/typing.lp",
    "safety/variables.lp",
    "safety/asp_safety.lp",
    "operators/comparisons.lp",
    "operators/arithmetic.lp",
    "operators/arithmetic_domain.lp",
    "operators/arithmetic_identities.lp",
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
    "core/output.lp",
)
HYPOTHESIS_SPACE_RULES = "\n".join(
    (Path(__file__).with_name("rules") / module).read_text()
    for module in HYPOTHESIS_SPACE_RULE_MODULES
)


@dataclass(frozen=True, slots=True)
class HypothesisMode:
    id: int
    recall_group: int
    section: str
    kind: str
    name: str
    arity: int
    recall: int
    positive: bool = True
    operator: str = ""
    aggregate_function: str = ""
    tuple_arity: int = 0
    aggregate_atoms: tuple[tuple[str, int], ...] = ()
    arg_types: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class HypothesisCapabilities:
    has_numeric_evidence: bool
    allow_numeric_comparison: bool
    allow_equality_comparison: bool
    allow_arithmetic: bool
    allow_aggregates: bool
    allow_recursion: bool


@dataclass(frozen=True, slots=True)
class ReifiedLiteral:
    section: str
    slot: int
    mode_id: int
    variables: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ReifiedClause:
    head: tuple[ReifiedLiteral, ...]
    body: tuple[ReifiedLiteral, ...]

    def render(self, modes: dict[int, HypothesisMode]) -> str:
        head = ";".join(_render_literal(literal, modes[literal.mode_id]) for literal in self.head)
        body = ",".join(_render_literal(literal, modes[literal.mode_id]) for literal in self.body)
        return f"{head} :- {body}." if head else f":- {body}."


@dataclass(frozen=True, slots=True)
class ClosedWorldProperties:
    symmetric: frozenset[Predicate]
    asymmetric: frozenset[Predicate]
    antisymmetric: frozenset[Predicate]
    acyclic: frozenset[Predicate]
    reflexive: frozenset[Predicate]
    strict_order: frozenset[Predicate]
    total_order: frozenset[Predicate]
    inverse: frozenset[tuple[Predicate, Predicate]]
    implies: frozenset[tuple[Predicate, Predicate]]
    equivalent: frozenset[tuple[Predicate, Predicate]]
    project_implies: frozenset[tuple[Predicate, Predicate, tuple[int, ...]]]
    disjoint_projection: frozenset[tuple[Predicate, int, Predicate, int]]
    mutex: frozenset[tuple[Predicate, Predicate]]
    complement: frozenset[tuple[Predicate, Predicate]]
    partitions: frozenset[tuple[Predicate, ...]]
    universal: frozenset[Predicate]
    empty: frozenset[Predicate]
    arg_equal: frozenset[tuple[Predicate, int, int]]
    arg_distinct: frozenset[tuple[Predicate, int, int]]
    functional: frozenset[tuple[Predicate, int, int]]
    functional_set: frozenset[tuple[Predicate, tuple[int, ...], int]]
    keys: frozenset[tuple[Predicate, tuple[int, ...]]]
    cardinality_upper: frozenset[tuple[Predicate, int]]
    transitive: frozenset[Predicate]


def _rule_entry_from_clause(
    rendered: str,
    clause: ReifiedClause,
    modes: dict[int, HypothesisMode],
) -> RuleEntry:
    heads: set[Predicate] = set()
    deps: set[Predicate] = set()
    for literal in clause.head:
        mode = modes[literal.mode_id]
        if mode.kind == "normal":
            heads.add((mode.name, mode.arity))
    for literal in clause.body:
        mode = modes[literal.mode_id]
        if mode.kind == "normal":
            deps.add((mode.name, mode.arity))
        elif mode.kind == "aggregate":
            deps.update(mode.aggregate_atoms)
    return RuleEntry(rendered, frozenset(heads), frozenset(deps), len(clause.body))


class HypothesisSpaceGenerator:
    def __init__(self, program: Program, args: Arguments) -> None:
        self.program = program
        self.args = args
        self.fragments = _program_fragments(program)
        self.predicate_arg_types = _predicate_arg_types(program, self.fragments)
        self.aggregate_specs = _valid_aggregate_specs(program, self.fragments)
        self.capabilities = _hypothesis_capabilities(
            program, args, self.predicate_arg_types, self.aggregate_specs
        )
        self.modes = _hypothesis_modes(
            program, args, self.capabilities, self.predicate_arg_types, self.aggregate_specs
        )
        self.modes_by_id = {mode.id: mode for mode in self.modes}

    def generate(self) -> RuleSpace:
        program = (
            _facts(
                self.program,
                self.args,
                self.modes,
                self.capabilities,
                self.predicate_arg_types,
            )
            + "\n"
            + HYPOTHESIS_SPACE_RULES
        )
        ctl = clingo.Control(
            [str(self.args.max_candidate_clauses), *_hypothesis_space_args(self.args)],
            logger=wrapper_exit_callback,
        )
        ctl.add("base", [], program)
        start = time.perf_counter()
        ctl.ground([("base", [])])
        grounding_seconds = time.perf_counter() - start
        add(f"{current_phase()}.grounding", grounding_seconds)
        if metric_enabled("clingo"):
            with instrumentation():
                stats = ground_stats(ctl)
                record_metric(
                    "clingo",
                    {
                        "operation": "hypothesis_space_grounding",
                        "operation_category": "grounding",
                        "phase_context": current_phase(),
                        "seconds": grounding_seconds,
                        "program_size": 1,
                        "program_chars": len(program),
                        "stats_atoms": stats["atoms"],
                        "stats_rules": stats["rules"],
                        "clingo_arguments": " ".join(
                            [
                                str(self.args.max_candidate_clauses),
                                *_hypothesis_space_args(self.args),
                            ]
                        ),
                    },
                )

        clauses: dict[ReifiedClause, None] = {}
        start = time.perf_counter()
        models = 0
        collect_metrics = metric_enabled("clingo")
        with ctl.solve(yield_=True) as handle:  # type: ignore
            for model in handle:  # type: ignore
                if collect_metrics:
                    models += 1
                clauses.setdefault(
                    _clause_from_symbols(
                        model.symbols(shown=True),
                        self.modes_by_id,
                        self.args.max_variables,
                    ),
                    None,
                )

        seconds = time.perf_counter() - start
        phase = current_phase()
        add(f"{phase}.solving", seconds)
        if collect_metrics:
            with instrumentation():
                record_metric(
                    "clingo",
                    {
                        "operation": "hypothesis_space_solving",
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
                        "clingo_arguments": " ".join(
                            [
                                str(self.args.max_candidate_clauses),
                                *_hypothesis_space_args(self.args),
                            ]
                        ),
                    },
                )

        return RuleSpace(
            [
                _rule_entry_from_clause(
                    clause.render(self.modes_by_id),
                    clause,
                    self.modes_by_id,
                )
                for clause in clauses
            ]
        )


@profile_phase("hypothesis_space")
def build_hypothesis_space(program: Program, arguments: Arguments) -> RuleSpace:
    rule_space = HypothesisSpaceGenerator(program, arguments).generate()
    if metric_enabled("candidate"):
        with instrumentation():
            record_metric(
                "candidate",
                {
                    "metric": "hypothesis_space",
                    "clauses": len(rule_space),
                },
            )
    return rule_space


def _numeric_domain_values(program: Program) -> set[int]:
    fragments = [*program.background]
    for example in [*program.positive_examples, *program.negative_examples]:
        fragments.extend([example.included, example.excluded, example.context])
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
        values.update(int(value) for value in re.findall(r"(?<![\w-])-?\d+(?![\w])", fragment))
    return values


def _numeric_constants(fragments: list[str]) -> dict[str, int]:
    constants: dict[str, int] = {}
    for fragment in fragments:
        for name, value in re.findall(r"#const\s+([A-Za-z_]\w*)\s*=\s*(-?\d+)\s*\.", fragment):
            constants[name] = int(value)
    return constants


def _closed_world_extensions(fragments: list[str]) -> dict[Predicate, set[tuple[str, ...]]]:
    extensions: dict[Predicate, set[tuple[str, ...]]] = {}
    constants = _numeric_constants(fragments)
    for fragment in fragments:
        for name, arguments, _negative in fragment_atoms(fragment):
            if any(_is_variable(argument) for argument in arguments):
                continue
            key = (name, len(arguments))
            for values in _expand_ground_arguments(arguments, constants):
                extensions.setdefault(key, set()).add(values)
    return extensions


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


def _expand_ground_argument(argument: str, constants: dict[str, int]) -> list[str] | None:
    text = argument.strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    match = re.fullmatch(r"(-?\d+)\.\.([A-Za-z_]\w*|-?\d+)", text)
    if not match:
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
            if any(_is_variable(argument) for argument in arguments):
                continue
            arity = len(arguments)
            for values in _expand_ground_arguments(arguments, constants):
                for index, value in enumerate(values):
                    arg_type = predicate_arg_types.get((name, arity, index), "any")
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
            arg_type = predicate_arg_types.get((predicate[0], predicate[1], index), "any")
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
            if _is_variable(value):
                continue
            arg_type = predicate_arg_types.get((name, 1, 0), "any")
            values = _expand_ground_argument(value, constants)
            if arg_type != "any" and values is not None:
                domains.setdefault(arg_type, {}).setdefault((name, 1), set()).update(values)
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
            if all(left == right or (right, left) not in tuples for left, right in tuples):
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
                equivalent.add(tuple(sorted((left, right))))
            elif left_tuples <= right_tuples:
                implies.add((left, right))
            elif right_tuples <= left_tuples:
                implies.add((right, left))
            if left_tuples.isdisjoint(right_tuples):
                universe = tuple_universe_by_arity[left[1]]
                if left_tuples | right_tuples == universe:
                    complement.add(tuple(sorted((left, right))))
                else:
                    mutex.add(tuple(sorted((left, right))))
            if left[1] == 2 and left_tuples == {(b, a) for a, b in right_tuples}:
                inverse.add(tuple(sorted((left, right))))
        _collect_disjoint_projections(left, left_tuples, right, right_tuples, disjoint_projection)
        _collect_projection_implications(left, left_tuples, right, right_tuples, project_implies)
        _collect_projection_implications(right, right_tuples, left, left_tuples, project_implies)
    functional.update(choice_functional)
    functional_set.update(choice_functional_set)
    keys.update(choice_keys)
    project_implies.update(choice_project_implies)
    cardinality_upper.update(choice_cardinality_upper)
    _collect_rule_defined_properties(fragments, keys, functional, functional_set)
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
            if predicate not in extensions and predicate not in _defined_predicates(fragments)
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
                cardinality_upper[predicate] = cardinality_upper.get(predicate, 0) + upper
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
        project_implies.update(_choice_project_implies(predicate, head.elements, node.body))

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
    if any(atom_name != name or len(arguments) != arity for atom_name, arguments in atoms):
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
            ast.parse_string(fragment if fragment.strip().endswith(".") else f"{fragment}.", collect)
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
                _propagate_key_through_rule(head, body_atom, key, equalities, functional, functional_set, keys)


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
        square
        for square, root in equalities
        if root in determinant_vars
    }
    determinant_positions = tuple(
        index for index, argument in enumerate(head_args) if argument in determinant_vars
    )
    if not determinant_positions:
        return
    output_positions = tuple(
        index for index, argument in enumerate(head_args) if argument not in determinant_vars
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
    if symbol.ast_type != ast.ASTType.Function or not symbol.name:
        return None
    return str(symbol.name), tuple(symbol.arguments)


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
        projected = {tuple(values[arg] for arg in projection) for values in source_tuples}
        if projected <= target_tuples:
            project_implies.add((source, target, projection))


def _is_transitive(tuples: set[tuple[str, ...]]) -> bool:
    if len(tuples) < 3:
        return False
    for left, middle in tuples:
        for other_middle, right in tuples:
            if middle == other_middle and (left, right) not in tuples:
                return False
    return True


def _is_reflexive(tuples: set[tuple[str, str]]) -> bool:
    domain = {value for row in tuples for value in row}
    return bool(domain) and all((value, value) in tuples for value in domain)


def _is_total_order(tuples: set[tuple[str, str]]) -> bool:
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


def _recursive_predicates(program: Program) -> set[Predicate]:
    head_predicates = {(md.name, md.arity) for md in program.language_bias_head}
    generated = program.generated_language_bias_body
    return {
        (md.name, md.arity)
        for md in program.language_bias_body
        if md.positive
        and (md.name, md.arity) in head_predicates
        and (md.name, md.arity) not in generated
    }


def _hypothesis_capabilities(
    program: Program,
    args: Arguments,
    predicate_arg_types: dict[tuple[str, int, int], str],
    aggregate_specs: list[AggregateDeclaration],
) -> HypothesisCapabilities:
    numeric_evidence = any(
        arg_type == "numeric" for arg_type in predicate_arg_types.values()
    )
    comparison_operators = {mode.operator for mode in program.comparison_modes}
    equality_comparison = "neq" in comparison_operators
    numeric_comparison = numeric_evidence and bool(
        comparison_operators & {"lt", "leq", "gt", "geq"}
    )
    return HypothesisCapabilities(
        has_numeric_evidence=numeric_evidence,
        allow_numeric_comparison=numeric_comparison,
        allow_equality_comparison=equality_comparison,
        allow_arithmetic=numeric_evidence and bool(program.arithmetic_modes),
        allow_aggregates=bool(aggregate_specs),
        allow_recursion=bool(_recursive_predicates(program)),
    )


def _available_predicates(
    program: Program, fragments: list[str]
) -> set[tuple[str, int]]:
    predicates = {
        (mode.name, mode.arity)
        for mode in [*program.language_bias_head, *program.language_bias_body]
    }
    for fragment in fragments:
        for name, arguments, _negative in fragment_atoms(fragment):
            predicates.add((name, len(arguments)))
    return predicates


def _predicate_arg_types(
    program: Program, fragments: list[str]
) -> dict[tuple[str, int, int], str]:
    positions = {
        (mode.name, mode.arity, arg)
        for mode in [*program.language_bias_head, *program.language_bias_body]
        for arg in range(mode.arity)
    }
    constants_by_position: dict[tuple[str, int, int], set[str]] = {
        position: set() for position in positions
    }
    positions_by_constant: dict[str, set[tuple[str, int, int]]] = {}
    variable_position_groups: list[list[tuple[str, int, int]]] = []
    for fragment in fragments:
        positions_by_variable: dict[str, list[tuple[str, int, int]]] = {}
        for name, arguments, _negative in fragment_atoms(fragment):
            arity = len(arguments)
            for index, value in enumerate(arguments):
                position = (name, arity, index)
                positions.add(position)
                if _is_variable(value):
                    positions_by_variable.setdefault(value, []).append(position)
                else:
                    constants_by_position.setdefault(position, set()).add(value)
                    positions_by_constant.setdefault(value, set()).add(position)
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

    for shared_positions in positions_by_constant.values():
        items = list(shared_positions)
        for other in items[1:]:
            union(items[0], other)
    for shared_positions in variable_position_groups:
        for other in shared_positions[1:]:
            union(shared_positions[0], other)

    constants_by_root: dict[tuple[str, int, int], set[str]] = {}
    for position in positions:
        root = find(position)
        constants_by_root.setdefault(root, set()).update(
            constants_by_position.get(position, set())
        )

    type_by_root: dict[tuple[str, int, int], str] = {}
    next_type = 0
    for root, constants in constants_by_root.items():
        if constants and all(_is_numeric_constant(value) for value in constants):
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


def _program_fragments(program: Program) -> list[str]:
    fragments = [
        line
        for line in program.background
        if line.strip() and not line.lstrip().startswith("%")
    ]
    for example in [*program.positive_examples, *program.negative_examples]:
        fragments.extend([example.included, example.excluded, example.context])
    return [fragment for fragment in fragments if fragment.strip()]


def _closed_world_fragments(program: Program) -> list[str]:
    fragments = [
        line
        for line in program.background
        if line.strip() and not line.lstrip().startswith("%")
    ]
    for example in program.positive_examples:
        fragments.append(example.context)
    for example in program.negative_examples:
        fragments.append(example.context)
    return [fragment for fragment in fragments if fragment.strip()]


def _valid_aggregate_specs(
    program: Program,
    fragments: list[str] | None = None,
) -> list[AggregateDeclaration]:
    if not program.aggregate_modes:
        return []
    available = _available_predicates(program, fragments or _program_fragments(program))
    valid = []
    for spec in program.aggregate_modes:
        if all(atom in available for atom in spec.atoms):
            valid.append(spec)
    return valid


def _hypothesis_modes(
    program: Program,
    args: Arguments,
    capabilities: HypothesisCapabilities,
    predicate_arg_types: dict[tuple[str, int, int], str],
    aggregate_specs: list[AggregateDeclaration],
) -> list[HypothesisMode]:
    modes: list[HypothesisMode] = []
    next_id = 0
    head_predicates = {(md.name, md.arity) for md in program.language_bias_head}
    recursive_predicates = _recursive_predicates(program)

    def add(mode: HypothesisMode) -> None:
        nonlocal next_id
        modes.append(mode)
        next_id += 1

    for md in program.language_bias_head:
        add(
            HypothesisMode(
                id=next_id,
                recall_group=next_id,
                section="head",
                kind="normal",
                name=md.name,
                arity=md.arity,
                recall=md.recall,
                positive=True,
                arg_types=_normal_arg_types(md.name, md.arity, predicate_arg_types),
            )
        )
    for md in program.language_bias_body:
        if (
            md.positive
            and (md.name, md.arity) in head_predicates
            and (md.name, md.arity) not in recursive_predicates
        ):
            continue
        add(
            HypothesisMode(
                id=next_id,
                recall_group=next_id,
                section="body",
                kind="normal",
                name=md.name,
                arity=md.arity,
                recall=md.recall,
                positive=md.positive,
                arg_types=_normal_arg_types(md.name, md.arity, predicate_arg_types),
            )
        )

    comparison_operators = {declaration.operator for declaration in program.comparison_modes}
    for declaration in program.comparison_modes:
        if declaration.operator == "eq":
            continue
        if declaration.operator == "gt" and "lt" in comparison_operators:
            continue
        if declaration.operator == "geq" and "leq" in comparison_operators:
            continue
        symbol = {"lt": "<", "leq": "<=", "gt": ">", "geq": ">=", "eq": "==", "neq": "!="}.get(declaration.operator)
        numeric_operator = declaration.operator in {"lt", "leq", "gt", "geq"}
        equality_operator = declaration.operator in {"eq", "neq"}
        if symbol and (
            (numeric_operator and capabilities.allow_numeric_comparison)
            or (equality_operator and capabilities.allow_equality_comparison)
        ):
            arg_types = ("numeric", "numeric") if numeric_operator else ("any", "any")
            add(HypothesisMode(next_id, next_id, "body", "comparison", "", 2, declaration.recall, True, operator=symbol, arg_types=arg_types))

    if capabilities.allow_arithmetic:
        for declaration in program.arithmetic_modes:
            symbol = {"add": "+", "sub": "-", "mul": "*", "div": "/", "mod": "\\", "abs": "abs"}.get(declaration.operator)
            if symbol:
                add(HypothesisMode(next_id, next_id, "body", "arithmetic", "", 3, declaration.recall, True, operator=symbol, arg_types=("numeric", "numeric", "numeric")))

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
            condition_types = tuple(
                predicate_arg_types.get((name, arity, arg), "any")
                for name, arity in atoms
                for arg in range(arity)
            )
            add(
                HypothesisMode(
                    id=next_id,
                    recall_group=recall_group,
                    section="body",
                    kind="aggregate",
                    name="",
                    arity=tuple_arity + total_atom_arity + 1,
                    recall=declaration.recall,
                    positive=True,
                    aggregate_function=declaration.function,
                    tuple_arity=tuple_arity,
                    aggregate_atoms=tuple(atoms),
                    arg_types=("any",) * tuple_arity + condition_types + ("numeric",),
                )
            )
    return modes


def _normal_arg_types(
    name: str, arity: int, predicate_arg_types: dict[tuple[str, int, int], str]
) -> tuple[str, ...]:
    return tuple(predicate_arg_types.get((name, arity, arg), "any") for arg in range(arity))


def _closed_body_predicates(program: Program) -> set[Predicate]:
    head_predicates = {(mode.name, mode.arity) for mode in program.language_bias_head}
    return {
        (mode.name, mode.arity)
        for mode in program.language_bias_body
        if (mode.name, mode.arity) not in head_predicates
        and (mode.name, mode.arity) not in program.generated_language_bias_body
    }


def _facts(
    program: Program,
    args: Arguments,
    modes: list[HypothesisMode],
    capabilities: HypothesisCapabilities,
    predicate_arg_types: dict[tuple[str, int, int], str],
) -> str:
    fragments = _closed_world_fragments(program)
    properties = _closed_world_properties(
        fragments,
        predicate_arg_types,
        _closed_body_predicates(program),
    )
    predicate_ids = _predicate_ids(modes)
    parts = [
        f"max_depth({args.max_depth}).",
        f"max_head({args.disjunctive_head_length}).",
        f"max_vars({args.max_variables}).",
    ]
    domain = _numeric_domain_values(program)
    all_positive = bool(domain) and all(value > 0 for value in domain)
    if domain and 0 not in domain and not all_positive:
        parts.append("zero_not_in_numeric_domain.")
    if domain and all(value >= 0 for value in domain) and not all_positive:
        parts.append("numeric_domain_nonnegative.")
    if all_positive:
        parts.append("numeric_domain_positive.")
    parts.extend(_closed_world_property_facts(properties, predicate_ids))
    for mode in modes:
        section_id = mode.section
        predicate_id = mode.id
        if mode.kind == "normal":
            key = (mode.name, mode.arity)
            predicate_id = predicate_ids[key]
        recall = args.max_depth if mode.recall < 0 else mode.recall
        parts.append(f"mode({section_id},{mode.id},{predicate_id},{mode.arity},{recall}).")
        parts.append(f"recall_group({mode.id},{mode.recall_group}).")
        for index, arg_type in enumerate(mode.arg_types):
            if arg_type != "any":
                parts.append(f"mode_arg_type({mode.id},{index},{arg_type}).")
        if not mode.positive:
            parts.append(f"negative_mode({mode.id}).")
        if mode.kind == "comparison":
            if mode.operator == "!=":
                parts.append(f"neq_comparison_mode({mode.id}).")
            if mode.operator == "<":
                parts.append(f"less_than_comparison_mode({mode.id}).")
            elif mode.operator == ">":
                parts.append(f"greater_than_comparison_mode({mode.id}).")
            elif mode.operator == "<=":
                parts.append(f"leq_comparison_mode({mode.id}).")
            elif mode.operator == ">=":
                parts.append(f"geq_comparison_mode({mode.id}).")
        elif mode.kind == "arithmetic":
            if mode.operator == "+":
                parts.append(f"add_mode({mode.id}).")
            elif mode.operator == "-":
                parts.append(f"sub_mode({mode.id}).")
            elif mode.operator == "*":
                parts.append(f"mul_mode({mode.id}).")
            elif mode.operator == "/":
                parts.append(f"div_mode({mode.id}).")
            elif mode.operator == "\\":
                parts.append(f"mod_mode({mode.id}).")
            elif mode.operator == "abs":
                parts.append(f"abs_mode({mode.id}).")
        elif mode.kind == "aggregate":
            parts.append(
                f"aggregate_mode({mode.id},{mode.tuple_arity},{len(mode.aggregate_atoms)})."
            )
            if mode.aggregate_function == "count":
                parts.append(f"count_aggregate_mode({mode.id}).")
            offset = 0
            for atom_index, atom in enumerate(mode.aggregate_atoms):
                arity = atom[1]
                parts.append(
                    f"aggregate_condition_atom({mode.id},{atom_index},{predicate_ids[atom]},{offset},{arity})."
                )
                offset += arity
    return "\n".join(parts)


def _predicate_ids(modes: list[HypothesisMode]) -> dict[Predicate, int]:
    predicate_ids: dict[Predicate, int] = {}
    for mode in modes:
        if mode.kind == "normal":
            predicate_ids.setdefault((mode.name, mode.arity), len(predicate_ids))
        elif mode.kind == "aggregate":
            for atom in mode.aggregate_atoms:
                predicate_ids.setdefault(atom, len(predicate_ids))
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


def _clause_from_symbols(
    symbols: list[clingo.Symbol],
    modes: dict[int, HypothesisMode],
    max_variables: int,
) -> ReifiedClause:
    literals: list[ReifiedLiteral] = []
    for symbol in symbols:
        arguments = symbol.arguments
        section = "head" if arguments[0].number == 0 else "body"
        slot = arguments[1].number
        mode_id = arguments[2].number
        code = arguments[3].number
        literals.append(
            ReifiedLiteral(
                section,
                slot,
                mode_id,
                _decode_vars(code, modes[mode_id].arity, max_variables),
            )
        )

    head = tuple(
        literal
        for literal in sorted(literals, key=lambda literal: literal.slot)
        if literal.section == "head"
    )
    body = tuple(
        literal
        for literal in sorted(literals, key=lambda literal: literal.slot)
        if literal.section == "body"
    )
    return ReifiedClause(head=head, body=body)


@lru_cache(maxsize=None)
def _decode_vars(code: int, arity: int, max_variables: int) -> tuple[int, ...]:
    if arity == 0:
        return ()
    if max_variables <= 0:
        raise ValueError("max_variables must be positive for non-zero arity modes")
    values = [0] * arity
    for index in range(arity - 1, -1, -1):
        values[index] = code % max_variables
        code //= max_variables
    return tuple(values)


def _render_literal(literal: ReifiedLiteral, mode: HypothesisMode) -> str:
    variables = [f"V{var}" for var in literal.variables]
    if mode.kind == "normal":
        atom = f"{mode.name}({','.join(variables)})" if variables else mode.name
        return atom if mode.positive else f"not {atom}"
    if mode.kind == "comparison":
        return f"{variables[0]}{mode.operator}{variables[1]}"
    if mode.kind == "arithmetic":
        if mode.operator == "abs":
            return f"|{variables[0]}-{variables[1]}|={variables[2]}"
        return f"{variables[0]}{mode.operator}{variables[1]}={variables[2]}"
    if mode.kind == "aggregate":
        tuple_vars = variables[: mode.tuple_arity]
        atom_vars = variables[mode.tuple_arity : -1]
        result = variables[-1]
        atoms = []
        offset = 0
        for name, arity in mode.aggregate_atoms:
            args = atom_vars[offset : offset + arity]
            atoms.append(f"{name}({','.join(args)})")
            offset += arity
        return (
            f"#{mode.aggregate_function}"
            + "{"
            + ",".join(tuple_vars)
            + ":"
            + ",".join(atoms)
            + "}="
            + result
        )
    raise ValueError(f"Unknown hypothesis mode kind: {mode.kind}")


def _hypothesis_space_args(args: Arguments) -> list[str]:
    value = args.hypothesis_space.get("clingo_arguments", [])
    if isinstance(value, list):
        return [str(item) for item in value]
    raise ValueError("hypothesis_space.clingo_arguments must be a list")
