from .assumption_activation import AssumptionActivation
from .external_activation import ExternalActivation
from .normal_coverage_solver import NormalCoverageSolver
from .pregrounded_coverage_solver import PregroundedCoverageSolver
from ..rule_generation.example import Example


def create_coverage_solver(
    grounding: str,
    lines: list[str],
    clingo_arguments: list[str],
    interpretation_pos: list[Example],
    interpretation_neg: list[Example],
    *,
    rule_space: tuple[str, ...] | None = None,
    max_program_clauses: int | None = None,
):
    if grounding == "normal":
        return NormalCoverageSolver(
            lines, clingo_arguments, interpretation_pos, interpretation_neg
        )
    if rule_space is None:
        raise ValueError(f"grounding={grounding} requires a rule space")
    if max_program_clauses is None:
        raise ValueError(f"grounding={grounding} requires max program clauses")
    activations = {
        "externals": ExternalActivation,
        "assumptions": AssumptionActivation,
    }
    try:
        activation = activations[grounding]()
    except KeyError:
        raise ValueError(f"Unknown pre-grounding activation: {grounding}") from None
    return PregroundedCoverageSolver(
        lines,
        clingo_arguments,
        interpretation_pos,
        interpretation_neg,
        rule_space,
        activation,
        max_program_clauses,
    )
