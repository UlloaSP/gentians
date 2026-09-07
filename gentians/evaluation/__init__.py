from ..clauses import ClauseSpace
from ..language.asp import AspProgram
from ..language.ir.inductive_task import InductiveTask
from .evaluator import CandidateEvaluator
from .pool_solver import EpochPoolCoverageSolver
from .scoring import balanced_coverage_score, coverage_score
from .solver import CoverageSolver

SCORING_STRATEGIES = {
    "cov_program": coverage_score,
    "cov_balanced": balanced_coverage_score,
}


def create_evaluator(
    task: InductiveTask,
    config: dict[str, object],
) -> CandidateEvaluator:
    score, clingo_arguments = _evaluation_config(config)
    solver = CoverageSolver(
        task.background,
        clingo_arguments,
        task.positive_examples,
        task.negative_examples,
    )
    return CandidateEvaluator(task, solver, score)


def create_epoch_pool_evaluator(
    task: InductiveTask,
    config: dict[str, object],
    pool: ClauseSpace,
    *,
    coverage_program: AspProgram | None = None,
) -> CandidateEvaluator:
    score, clingo_arguments = _evaluation_config(config)
    return CandidateEvaluator(
        task,
        EpochPoolCoverageSolver(
            task, clingo_arguments, pool, coverage_program=coverage_program,
        ),
        score,
    )


def _evaluation_config(config: dict[str, object]):
    name = str(config["scoring"])
    try:
        score = SCORING_STRATEGIES[name]
    except KeyError:
        raise ValueError(f"Unknown scoring strategy: {name}") from None
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
    return score, ["0", "--enum-mode=brave", *clingo_arguments]
