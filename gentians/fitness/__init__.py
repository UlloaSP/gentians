from ..asp.normal_coverage_solver import NormalCoverageSolver
from ..language.ir.inductive_task import InductiveTask
from .evaluator import FitnessEvaluator
from .scoring import balanced_coverage_score, coverage_score

FITNESS_STRATEGIES = {
    "cov_program": coverage_score,
    "cov_balanced": balanced_coverage_score,
}


def create_fitness(
    task: InductiveTask,
    config: dict[str, object],
):
    name = str(config["name"])
    try:
        score = FITNESS_STRATEGIES[name]
    except KeyError:
        raise ValueError(f"Unknown fitness strategy: {name}") from None
    configured_arguments = config.get("clingo_arguments", [])
    if not isinstance(configured_arguments, list):
        raise ValueError("fitness.clingo_arguments must be a list")
    values = iter(str(value) for value in configured_arguments)
    clingo_arguments = []
    for value in values:
        if value == "--enum-mode":
            next(values, None)
        elif not value.startswith("--enum-mode="):
            clingo_arguments.append(value)
    solver = NormalCoverageSolver(
        task.background,
        ["0", "--enum-mode=brave", *clingo_arguments],
        task.positive_examples,
        task.negative_examples,
    )
    return FitnessEvaluator(task, solver, score)
