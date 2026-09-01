from dataclasses import dataclass

from .hypothesis_mode import HypothesisMode
from .reified_literal import ReifiedLiteral


@dataclass(frozen=True, slots=True)
class ReifiedClause:
    head: tuple[ReifiedLiteral, ...]
    body: tuple[ReifiedLiteral, ...]


def _render_literal(literal: ReifiedLiteral, mode: HypothesisMode) -> str:
    variables = [f"V{var}" for var in literal.variables]
    if mode.kind == "normal":
        variable_iterator = iter(variables)
        arguments = [
            next(variable_iterator) if fixed is None else fixed
            for fixed in mode.fixed_arguments
        ]
        atom = (
            f"{mode.name}({','.join(arguments)})" if arguments else mode.name
        )
        return atom if mode.positive else f"not {atom}"
    if mode.kind == "comparison":
        return f"{variables[0]}{mode.operator}{variables[1]}"
    if mode.kind == "arithmetic":
        arithmetic = mode.arithmetic
        if arithmetic is None:
            raise ValueError(f"arithmetic mode {mode.id} has no template")
        if arithmetic.linear:
            output = variables[-1]
            positive = [
                variable
                for variable, coefficient in zip(
                    variables, arithmetic.coefficients
                )
                if coefficient > 0
            ]
            negative_inputs = [
                variable
                for variable, coefficient in zip(
                    variables[:-1], arithmetic.coefficients[:-1]
                )
                if coefficient < 0
            ]
            expression = "+".join(positive)
            if negative_inputs:
                expression += "-" + "-".join(negative_inputs)
            return f"{expression}={output}"
        if arithmetic.operator == "abs":
            return f"|{variables[0]}-{variables[1]}|={variables[2]}"
        return f"{variables[0]}{arithmetic.operator}{variables[1]}={variables[2]}"
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


def render_head(
    head: tuple[ReifiedLiteral, ...], modes: dict[int, HypothesisMode]
) -> str:
    if not head:
        return ""
    head_modes = tuple(modes[literal.mode_id] for literal in head)
    form = head_modes[0].head_form
    if form is None or any(mode.head_form != form for mode in head_modes):
        raise ValueError("rule head does not belong to one complete #modeh form")
    atoms = tuple(
        _render_literal(literal, mode)
        for literal, mode in zip(head, head_modes, strict=True)
    )
    kind = head_modes[0].head_kind
    if kind == "normal":
        if len(atoms) != 1:
            raise ValueError("normal #modeh form must contain one atom")
        return atoms[0]
    if kind == "disjunction":
        return ";".join(atoms)
    if kind == "choice":
        lower = "" if head_modes[0].head_lower is None else head_modes[0].head_lower
        upper = "" if head_modes[0].head_upper is None else head_modes[0].head_upper
        return f"{lower}{{{';'.join(atoms)}}}{upper}"
    raise ValueError(f"unknown #modeh form kind: {kind}")
