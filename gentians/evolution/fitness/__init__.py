from ...rule_generation.program import Program
from ...rule_generation.rule_space import RuleSpace
from .cov_program import CovProgram
from .trigram_cov import TrigramCov

FITNESS_STRATEGIES = {
    "cov_program": CovProgram,
    "trigram_cov": TrigramCov,
}


def create_fitness(
    program: Program,
    config: dict[str, object],
    max_program_clauses: int,
    rule_space: RuleSpace,
):
    name = str(config["name"])
    try:
        strategy = FITNESS_STRATEGIES[name]
    except KeyError:
        raise ValueError(f"Unknown fitness strategy: {name}")
    return strategy.from_config(
        program,
        config,
        max_program_clauses,
        rule_space,
    )
