from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time

import clingo

from ..arguments import Arguments
from ..asp.callbacks import wrapper_exit_callback
from ..timing import add, current_phase, record_metric
from .placed_clause import PlacedClause
from .program import ModeDeclaration, Program


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
        self.modes = _hypothesis_modes(program, args)
        self.modes_by_id = {mode.id: mode for mode in self.modes}

    def generate(self) -> tuple[list[list[str]], list[PlacedClause]]:
        program = _facts(self.args, self.modes) + "\n" + HYPOTHESIS_SPACE_RULES
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
                "clingo_arguments": " ".join(
                    [str(self.args.clauses_to_sample), *_hypothesis_space_args(self.args)]
                ),
            },
        )

        unique = [[clause] for clause in sorted(dict.fromkeys(clauses))]
        return unique, [PlacedClause(group) for group in unique]


def _hypothesis_modes(program: Program, args: Arguments) -> list[HypothesisMode]:
    modes: list[HypothesisMode] = []
    next_id = 0

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
            )
        )
    for md in program.language_bias_body:
        add(
            HypothesisMode(
                id=next_id,
                section="body",
                kind="normal",
                name=md.name,
                arity=md.arity,
                recall=md.recall,
                positive=md.positive,
            )
        )

    for operator in args.comparison_operators:
        symbol = {"lt": "<", "leq": "<=", "gt": ">", "geq": ">=", "eq": "==", "neq": "!="}.get(operator)
        if symbol:
            add(HypothesisMode(next_id, "body", "comparison", "", 2, 1, True, operator=symbol))

    for operator in args.arithmetic_operators:
        symbol = {"add": "+", "sub": "-", "mul": "*", "div": "/", "abs": "abs"}.get(operator)
        if symbol:
            add(HypothesisMode(next_id, "body", "arithmetic", "", 3, 1, True, operator=symbol))

    aggregate_specs = [_aggregate_spec(spec) for spec in args.aggregates]
    for function, atoms in aggregate_specs:
        total_atom_arity = sum(arity for _, arity in atoms)
        tuple_arities = (
            range(1, total_atom_arity + 1)
            if args.unbalanced_aggregates
            else [total_atom_arity]
        )
        for tuple_arity in tuple_arities:
            add(
                HypothesisMode(
                    id=next_id,
                    section="body",
                    kind="aggregate",
                    name="",
                    arity=tuple_arity + total_atom_arity + 1,
                    recall=1,
                    positive=True,
                    aggregate_function=function,
                    tuple_arity=tuple_arity,
                    aggregate_atoms=tuple(atoms),
                )
            )
    return modes


def _aggregate_spec(spec: str) -> tuple[str, list[tuple[str, int]]]:
    name, rest = spec.split("(", 1)
    atoms = rest.rstrip(")")
    pairs: list[tuple[str, int]] = []
    for atom in atoms.split(","):
        predicate, arity = atom.split("/", 1)
        pairs.append((predicate, int(arity)))
    return name, pairs


def _facts(args: Arguments, modes: list[HypothesisMode]) -> str:
    parts = [
        f"max_head({args.disjunctive_head_length}).",
        f"max_body({args.max_depth}).",
        f"max_vars({args.max_variables}).",
    ]
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
            for index, (_, arity) in enumerate(mode.aggregate_atoms):
                parts.append(f"aggregate_atom({mode.id},{index},{arity}).")
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
