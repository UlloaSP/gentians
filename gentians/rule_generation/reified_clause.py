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
