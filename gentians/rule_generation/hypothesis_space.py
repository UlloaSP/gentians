from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import time

import clingo

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


LOGIC_PROGRAMS = Path(__file__).parents[1] / "logic_programs"
HYPOTHESIS_SPACE_RULES = (LOGIC_PROGRAMS / "hypothesis_space_reified.lp").read_text()


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
    allow_constraints: bool


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
                        "allow_constraints": self.capabilities.allow_constraints,
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
    equality_comparison = bool(comparison_operators & {"eq", "neq"})
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
        allow_constraints=bool(program.negative_examples) or not program.language_bias_head,
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


def _inferred_irreflexive_predicates(fragments: list[str]) -> set[Predicate]:
    seen: set[Predicate] = set()
    repeated: set[Predicate] = set()
    unknown: set[Predicate] = set()
    for fragment in fragments:
        for name, arguments, _negative in fragment_atoms(fragment):
            arity = len(arguments)
            if arity < 2:
                continue
            predicate = (name, arity)
            seen.add(predicate)
            if any(_is_variable(argument) for argument in arguments):
                unknown.add(predicate)
            if len(set(arguments)) < len(arguments):
                repeated.add(predicate)
    return seen - repeated - unknown


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

    for declaration in program.comparison_modes:
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


def _facts(
    program: Program,
    args: Arguments,
    modes: list[HypothesisMode],
    capabilities: HypothesisCapabilities,
    predicate_arg_types: dict[tuple[str, int, int], str],
) -> str:
    max_body = args.max_depth if capabilities.allow_constraints else max(0, args.max_depth - 1)
    irreflexive = _inferred_irreflexive_predicates(_program_fragments(program))
    parts = [
        f"max_depth({args.max_depth}).",
        f"max_head({args.disjunctive_head_length}).",
        f"max_body({max_body}).",
        f"max_vars({args.max_variables}).",
    ]
    if capabilities.allow_constraints:
        parts.append("constraints_allowed.")
    parts.append("prune_redundant_comparisons.")
    parts.append("prune_arithmetic_identities.")
    parts.append("canonical_prune.")
    domain = _numeric_domain_values(program)
    if domain and 0 not in domain:
        parts.append("zero_not_in_numeric_domain.")
    predicate_ids: dict[tuple[str, int], int] = {}
    for mode in modes:
        section_id = mode.section
        predicate_id = mode.id
        if mode.kind == "normal":
            key = (mode.name, mode.arity)
            if key not in predicate_ids:
                predicate_ids[key] = len(predicate_ids)
            predicate_id = predicate_ids[key]
        recall = args.max_depth if mode.recall < 0 else mode.recall
        parts.append(f"mode({section_id},{mode.id},{predicate_id},{mode.arity},{recall}).")
        parts.append(f"recall({mode.id},{recall}).")
        parts.append(f"recall_group({mode.id},{mode.recall_group}).")
        for index, arg_type in enumerate(mode.arg_types):
            parts.append(f"mode_arg_type({mode.id},{index},{arg_type}).")
            if (
                mode.kind == "normal"
                and predicate_arg_types.get((mode.name, mode.arity, index)) == "numeric"
            ):
                parts.append(f"domain_numeric_arg({predicate_id},{mode.arity},{index}).")
        if mode.positive:
            parts.append(f"positive_mode({mode.id}).")
        else:
            parts.append(f"negative_mode({mode.id}).")
        if mode.kind == "normal":
            parts.append(f"normal_mode({mode.id}).")
            if (mode.name, mode.arity) in irreflexive:
                parts.append(f"irreflexive_mode({mode.id}).")
        elif mode.kind == "comparison":
            parts.append(f"comparison_mode({mode.id},{mode.id}).")
            if mode.operator in {"==", "!="}:
                parts.append(f"symmetric_comparison_mode({mode.id}).")
        elif mode.kind == "arithmetic":
            parts.append(f"arithmetic_mode({mode.id},{mode.id}).")
            if mode.operator == "+":
                parts.append(f"add_mode({mode.id}).")
            elif mode.operator == "-":
                parts.append(f"sub_mode({mode.id}).")
        elif mode.kind == "aggregate":
            parts.append(
                f"aggregate_mode({mode.id},{mode.tuple_arity},{len(mode.aggregate_atoms)})."
            )
    return "\n".join(parts)


def _clause_from_symbols(
    symbols: list[clingo.Symbol],
    modes: dict[int, HypothesisMode],
    max_variables: int,
) -> ReifiedClause:
    literals: list[ReifiedLiteral] = []
    for symbol in symbols:
        if symbol.name != "lit":
            continue
        section = symbol.arguments[0].name
        slot = symbol.arguments[1].number
        mode_id = symbol.arguments[2].number
        code = symbol.arguments[3].number
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
