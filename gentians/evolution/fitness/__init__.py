from .cov_program import CovProgram
from .cov_subprograms_max import CovSubprogramsMax
from .cov_subprograms_mean import CovSubprogramsMean
from .trigram_cov import TrigramCov
from ...rule_generation.program import Program
from ...rule_generation.rule_space import RuleSpace


FITNESS_STRATEGIES = {
    "cov_subprograms_mean": CovSubprogramsMean,
    "cov_subprograms_max": CovSubprogramsMax,
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
