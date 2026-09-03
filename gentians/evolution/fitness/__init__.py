from ...language.ir.inductive_task import InductiveTask
from .cov_balanced import CovBalanced
from .cov_program import CovProgram

FITNESS_STRATEGIES = {
    "cov_program": CovProgram,
    "cov_balanced": CovBalanced,
}


def create_fitness(
    task: InductiveTask,
    config: dict[str, object],
):
    name = str(config["name"])
    try:
        strategy = FITNESS_STRATEGIES[name]
    except KeyError:
        raise ValueError(f"Unknown fitness strategy: {name}") from None
    return strategy.from_config(task, config)
