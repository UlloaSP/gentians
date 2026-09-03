from ...clauses.program import Program
from .cov_balanced import CovBalanced
from .cov_program import CovProgram

FITNESS_STRATEGIES = {
    "cov_program": CovProgram,
    "cov_balanced": CovBalanced,
}


def create_fitness(
    program: Program,
    config: dict[str, object],
):
    name = str(config["name"])
    try:
        strategy = FITNESS_STRATEGIES[name]
    except KeyError:
        raise ValueError(f"Unknown fitness strategy: {name}") from None
    return strategy.from_config(program, config)
