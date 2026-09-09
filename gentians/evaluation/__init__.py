from ..clauses import ClauseSpace
from ..language.ir.inductive_task import InductiveTask
from .evaluator import CandidateEvaluator
from .scoring import coverage_score
from .solver import CoverageSolver


def create_evaluator(
    task: InductiveTask,
    config: dict[str, object],
    *,
    space: ClauseSpace | None = None,
) -> CandidateEvaluator:
    score, clingo_arguments = _evaluation_config(config)
    inheritance = config.get("constraint_inheritance", False)
    if not isinstance(inheritance, bool):
        raise ValueError("evaluation.constraint_inheritance must be a boolean")
    # Without learnable constraints, distinct candidates cannot have equal
    # headed programs. The search already memoizes identical genomes.
    if inheritance and space is not None and all(clause.heads for clause in space.entries):
        inheritance = False
    solver = CoverageSolver(
        task.background,
        clingo_arguments,
        task.positive_examples,
        task.negative_examples,
        constraint_inheritance=inheritance,
    )
    return CandidateEvaluator(task, solver, score)


def _evaluation_config(config: dict[str, object]):
    name = str(config["scoring"])
    if name != "cov_program":
        raise ValueError(f"Unknown scoring strategy: {name}")
    configured_arguments = config.get("clingo_arguments", [])
    if not isinstance(configured_arguments, list):
        raise ValueError("evaluation.clingo_arguments must be a list")
    values = iter(str(value) for value in configured_arguments)
    clingo_arguments = []
    for value in values:
        if value == "--enum-mode":
            next(values, None)
        elif not value.startswith("--enum-mode="):
            clingo_arguments.append(value)
    return coverage_score, ["0", "--enum-mode=brave", *clingo_arguments]
