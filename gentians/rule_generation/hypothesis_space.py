from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
from pathlib import Path
import re
import time

import clingo
from clingo import ast

from ..arguments import Arguments
from ..asp.callbacks import wrapper_exit_callback
from ..asp.rule_analysis import get_atoms
from ..timing import add, current_phase, record_metric
from .placed_clause import PlacedClause
from .parser_atoms import extract_name_arity
from .program import Program


LOGIC_PROGRAMS = Path(__file__).parents[1] / "logic_programs"
HYPOTHESIS_SPACE_RULES = (LOGIC_PROGRAMS / "hypothesis_space_reified.lp").read_text()


@dataclass(frozen=True)
class HypothesisMode:
    id: int
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


@dataclass(frozen=True)
class HypothesisCapabilities:
    has_numeric_evidence: bool
    allow_numeric_comparison: bool
    allow_equality_comparison: bool
    allow_arithmetic: bool
    allow_aggregates: bool
    allow_recursion: bool
    allow_constraints: bool


@dataclass(frozen=True)
class ReifiedLiteral:
    section: str
    slot: int
    mode_id: int
    variables: tuple[int, ...]


@dataclass(frozen=True)
class ReifiedClause:
    head: tuple[ReifiedLiteral, ...]
    body: tuple[ReifiedLiteral, ...]

    def render(self, modes: dict[int, HypothesisMode]) -> str:
        head = ";".join(_render_literal(literal, modes[literal.mode_id]) for literal in self.head)
        body = ",".join(_render_literal(literal, modes[literal.mode_id]) for literal in self.body)
        return f"{head} :- {body}." if head else f":- {body}."


class HypothesisSpaceGenerator:
    def __init__(self, program: Program, args: Arguments) -> None:
        self.program = program
        self.args = args
        self.predicate_arg_types = _predicate_arg_types(program)
        self.capabilities = _hypothesis_capabilities(
            program, args, self.predicate_arg_types
        )
        self.modes = _hypothesis_modes(
            program, args, self.capabilities, self.predicate_arg_types
        )
        self.modes_by_id = {mode.id: mode for mode in self.modes}

    def generate(self) -> tuple[list[list[str]], list[PlacedClause]]:
        program = _facts(self.args, self.modes, self.capabilities) + "\n" + HYPOTHESIS_SPACE_RULES
        ctl = clingo.Control(
            [str(self.args.clauses_to_sample), *_hypothesis_space_args(self.args)],
            logger=wrapper_exit_callback,
        )
        ctl.add("base", [], program)
        start = time.perf_counter()
        ctl.ground([("base", [])])
        add(f"{current_phase()}.grounding", time.perf_counter() - start)

        clauses: list[str] = []
        start = time.perf_counter()
        models = 0
        with ctl.solve(yield_=True) as handle:  # type: ignore
            for model in handle:  # type: ignore
                models += 1
                clause = _clause_from_symbols(model.symbols(shown=True))
                rendered = clause.render(self.modes_by_id)
                clauses.append(rendered)

        seconds = time.perf_counter() - start
        add("hypothesis_space.solving", seconds)
        record_metric(
            "clingo",
            {
                "operation": "hypothesis_space",
                "phase_context": current_phase(),
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
                    [str(self.args.clauses_to_sample), *_hypothesis_space_args(self.args)]
                ),
            },
        )

        unique = [[clause] for clause in sorted(dict.fromkeys(clauses))]
        return unique, [PlacedClause(group) for group in unique]


def _hypothesis_capabilities(
    program: Program,
    args: Arguments,
    predicate_arg_types: dict[tuple[str, int, int], str],
) -> HypothesisCapabilities:
    numeric_evidence = any(
        arg_type == "numeric" for arg_type in predicate_arg_types.values()
    )
    comparison_operators = set(args.comparison_operators)
    equality_comparison = bool(comparison_operators & {"eq", "neq"})
    numeric_comparison = numeric_evidence and bool(
        comparison_operators & {"lt", "leq", "gt", "geq"}
    )
    aggregates = _valid_aggregate_specs(program, args)
    return HypothesisCapabilities(
        has_numeric_evidence=numeric_evidence,
        allow_numeric_comparison=numeric_comparison,
        allow_equality_comparison=equality_comparison,
        allow_arithmetic=numeric_evidence and bool(args.arithmetic_operators),
        allow_aggregates=bool(aggregates),
        allow_recursion=bool(args.sampling.get("enable_recursion", False)),
        allow_constraints=bool(
            args.hypothesis_space.get(
                "allow_constraints",
                bool(program.negative_examples) or not program.language_bias_head,
            )
        ),
    )


def _available_predicates(program: Program) -> set[tuple[str, int]]:
    predicates = {
        (mode.name, mode.arity)
        for mode in [*program.language_bias_head, *program.language_bias_body]
    }
    for fragment in _program_fragments(program):
        for atom in _atoms_in_fragment(fragment):
            if atom.startswith("#"):
                continue
            predicates.add(extract_name_arity(atom))
    return predicates


def _predicate_arg_types(program: Program) -> dict[tuple[str, int, int], str]:
    positions = {
        (mode.name, mode.arity, arg)
        for mode in [*program.language_bias_head, *program.language_bias_body]
        for arg in range(mode.arity)
    }
    constants_by_position: dict[tuple[str, int, int], set[str]] = {
        position: set() for position in positions
    }
    positions_by_constant: dict[str, set[tuple[str, int, int]]] = {}
    for fragment in _program_fragments(program):
        for atom in _atoms_in_fragment(fragment):
            parsed = _parse_normal_atom(atom)
            if parsed is None:
                continue
            name, arguments = parsed
            arity = len(arguments)
            for index, value in enumerate(arguments):
                position = (name, arity, index)
                positions.add(position)
                constants_by_position.setdefault(position, set()).add(value)
                positions_by_constant.setdefault(value, set()).add(position)

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

    constants_by_root: dict[tuple[str, int, int], set[str]] = {}
    for position in positions:
        root = find(position)
        constants_by_root.setdefault(root, set()).update(
            constants_by_position.get(position, set())
        )

    type_by_root: dict[tuple[str, int, int], str] = {}
    next_type = 0
    for root, constants in constants_by_root.items():
        if constants and all(_is_number(value) for value in constants):
            type_by_root[root] = "numeric"
        elif constants:
            type_by_root[root] = f"type_{next_type}"
            next_type += 1
        else:
            type_by_root[root] = "any"

    return {position: type_by_root[find(position)] for position in positions}


def _parse_normal_atom(atom: str) -> tuple[str, list[str]] | None:
    normalized = atom.removeprefix("not")
    if normalized.startswith("#"):
        return None
    match = re.match(r"^([A-Za-z_]\w*)(?:\((.*)\))?$", normalized)
    if not match:
        return None
    arguments = match.group(2)
    if arguments is None or arguments == "":
        return match.group(1), []
    return match.group(1), [part.strip() for part in arguments.split(",")]


def _is_number(value: str) -> bool:
    return bool(re.fullmatch(r"[-+]?\d+", value))


def _program_fragments(program: Program) -> list[str]:
    fragments = [
        line
        for line in program.background
        if line.strip() and not line.lstrip().startswith("%")
    ]
    for example in [*program.positive_examples, *program.negative_examples]:
        fragments.extend([example.included, example.excluded, example.context])
    return [fragment for fragment in fragments if fragment.strip()]


def _atoms_in_fragment(fragment: str) -> list[str]:
    candidate = fragment.strip()
    if not candidate.endswith("."):
        candidate = f":- {candidate}."
    try:
        return get_atoms(candidate)
    except (RuntimeError, IndexError):
        atoms: list[str] = []
        ast.parse_string(candidate, lambda stm: _collect_symbolic_atoms(stm, atoms))
        return atoms


def _collect_symbolic_atoms(node: ast.AST, atoms: list[str]) -> None:
    if node.ast_type == ast.ASTType.SymbolicAtom:
        atoms.append(str(node.symbol).replace(" ", ""))
    for key in node.child_keys:
        child = getattr(node, key)
        if isinstance(child, ast.AST):
            _collect_symbolic_atoms(child, atoms)
        elif isinstance(child, list):
            for item in child:
                if isinstance(item, ast.AST):
                    _collect_symbolic_atoms(item, atoms)


def _valid_aggregate_specs(program: Program, args: Arguments) -> list[tuple[str, list[tuple[str, int]]]]:
    available = _available_predicates(program)
    valid = []
    for spec in args.aggregates:
        function, atoms = _aggregate_spec(spec)
        if all(atom in available for atom in atoms):
            valid.append((function, atoms))
    return valid


def _hypothesis_modes(
    program: Program,
    args: Arguments,
    capabilities: HypothesisCapabilities,
    predicate_arg_types: dict[tuple[str, int, int], str],
) -> list[HypothesisMode]:
    modes: list[HypothesisMode] = []
    next_id = 0
    head_predicates = {(md.name, md.arity) for md in program.language_bias_head}

    def add(mode: HypothesisMode) -> None:
        nonlocal next_id
        modes.append(mode)
        next_id += 1

    for md in program.language_bias_head:
        add(
            HypothesisMode(
                id=next_id,
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
            not capabilities.allow_recursion
            and md.positive
            and (md.name, md.arity) in head_predicates
        ):
            continue
        add(
            HypothesisMode(
                id=next_id,
                section="body",
                kind="normal",
                name=md.name,
                arity=md.arity,
                recall=md.recall,
                positive=md.positive,
                arg_types=_normal_arg_types(md.name, md.arity, predicate_arg_types),
            )
        )

    for operator, recall in Counter(args.comparison_operators).items():
        symbol = {"lt": "<", "leq": "<=", "gt": ">", "geq": ">=", "eq": "==", "neq": "!="}.get(operator)
        numeric_operator = operator in {"lt", "leq", "gt", "geq"}
        equality_operator = operator in {"eq", "neq"}
        if symbol and (
            (numeric_operator and capabilities.allow_numeric_comparison)
            or (equality_operator and capabilities.allow_equality_comparison)
        ):
            arg_types = ("numeric", "numeric") if numeric_operator else ("any", "any")
            add(HypothesisMode(next_id, "body", "comparison", "", 2, recall, True, operator=symbol, arg_types=arg_types))

    if capabilities.allow_arithmetic:
        for operator, recall in Counter(args.arithmetic_operators).items():
            symbol = {"add": "+", "sub": "-", "mul": "*", "div": "/", "abs": "abs"}.get(operator)
            if symbol:
                add(HypothesisMode(next_id, "body", "arithmetic", "", 3, recall, True, operator=symbol, arg_types=("numeric", "numeric", "numeric")))

    aggregate_specs = Counter(
        (function, tuple(atoms)) for function, atoms in _valid_aggregate_specs(program, args)
    )
    for (function, atoms_tuple), recall in aggregate_specs.items():
        atoms = list(atoms_tuple)
        total_atom_arity = sum(arity for _, arity in atoms)
        tuple_arities = (
            range(1, total_atom_arity + 1)
            if args.unbalanced_aggregates
            else [total_atom_arity]
        )
        for tuple_arity in tuple_arities:
            condition_types = tuple(
                predicate_arg_types.get((name, arity, arg), "any")
                for name, arity in atoms
                for arg in range(arity)
            )
            add(
                HypothesisMode(
                    id=next_id,
                    section="body",
                    kind="aggregate",
                    name="",
                    arity=tuple_arity + total_atom_arity + 1,
                    recall=recall,
                    positive=True,
                    aggregate_function=function,
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


def _aggregate_spec(spec: str) -> tuple[str, list[tuple[str, int]]]:
    name, rest = spec.split("(", 1)
    atoms = rest.rstrip(")")
    pairs: list[tuple[str, int]] = []
    for atom in atoms.split(","):
        predicate, arity = atom.split("/", 1)
        pairs.append((predicate, int(arity)))
    return name, pairs


def _facts(
    args: Arguments, modes: list[HypothesisMode], capabilities: HypothesisCapabilities
) -> str:
    parts = [
        f"max_depth({args.max_depth}).",
        f"max_head({args.disjunctive_head_length}).",
        f"max_body({args.max_depth}).",
        f"max_vars({args.max_variables}).",
    ]
    if capabilities.allow_constraints:
        parts.append("constraints_allowed.")
    predicate_ids: dict[tuple[str, int], int] = {}
    for mode in modes:
        section_id = mode.section
        predicate_id = mode.id
        if mode.kind == "normal":
            key = (mode.name, mode.arity)
            if key not in predicate_ids:
                predicate_ids[key] = len(predicate_ids)
            predicate_id = predicate_ids[key]
        parts.append(
            f"mode({section_id},{mode.id},{predicate_id},{mode.arity},{mode.recall})."
        )
        parts.append(f"recall({mode.id},{mode.recall}).")
        for index, arg_type in enumerate(mode.arg_types):
            parts.append(f"mode_arg_type({mode.id},{index},{arg_type}).")
        if mode.positive:
            parts.append(f"positive_mode({mode.id}).")
        else:
            parts.append(f"negative_mode({mode.id}).")
        if mode.kind == "normal":
            parts.append(f"normal_mode({mode.id}).")
        elif mode.kind == "comparison":
            parts.append(f"comparison_mode({mode.id},{mode.id}).")
        elif mode.kind == "arithmetic":
            parts.append(f"arithmetic_mode({mode.id},{mode.id}).")
        elif mode.kind == "aggregate":
            parts.append(
                f"aggregate_mode({mode.id},{mode.tuple_arity},{len(mode.aggregate_atoms)})."
            )
    return "\n".join(parts)


def _clause_from_symbols(symbols: list[clingo.Symbol]) -> ReifiedClause:
    selected: dict[tuple[str, int], int] = {}
    vars_by_literal: dict[tuple[str, int], dict[int, int]] = {}
    for symbol in symbols:
        if symbol.name == "selected":
            section = symbol.arguments[0].name
            slot = symbol.arguments[1].number
            mode_id = symbol.arguments[2].number
            selected[(section, slot)] = mode_id
        elif symbol.name == "var_at":
            section = symbol.arguments[0].name
            slot = symbol.arguments[1].number
            arg = symbol.arguments[2].number
            var = symbol.arguments[3].number
            vars_by_literal.setdefault((section, slot), {})[arg] = var

    def literal(section: str, slot: int, mode_id: int) -> ReifiedLiteral:
        args = vars_by_literal[(section, slot)]
        return ReifiedLiteral(
            section,
            slot,
            mode_id,
            tuple(args[index] for index in range(len(args))),
        )

    head = tuple(
        literal(section, slot, mode_id)
        for (section, slot), mode_id in sorted(selected.items())
        if section == "head"
    )
    body = tuple(
        literal(section, slot, mode_id)
        for (section, slot), mode_id in sorted(selected.items())
        if section == "body"
    )
    return ReifiedClause(head=head, body=body)


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
        return [str(item) for item in value if not str(item).isdigit()]
    if isinstance(value, str):
        return [] if value.isdigit() else [value]
    return []
