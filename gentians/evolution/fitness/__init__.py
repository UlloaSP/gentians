from ...rule_generation.program import Program
from .cov_program import CovProgram
from .trigram_cov import TrigramCov

FITNESS_STRATEGIES = {
    "cov_program": CovProgram,
    "trigram_cov": TrigramCov,
}


def create_fitness(
    program: Program,
    config: dict[str, object],
):
    name = str(config["name"])
    try:
        strategy = FITNESS_STRATEGIES[name]
    except KeyError:
        raise ValueError(f"Unknown fitness strategy: {name}")
    return strategy.from_config(program, config)
