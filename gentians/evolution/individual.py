import time
from dataclasses import dataclass, field

from .types import Behavior, FitnessResult, Genome, ProgramText


@dataclass(slots=True)
class Individual:
    program: Genome
    score: float
    is_best: bool  # does this cover everything positive and no negative?
    best_program: ProgramText | None = None
    behavior: Behavior = (0, 0)
    generated_timestamp: float = field(default_factory=time.time)

    def __str__(self) -> str:
        return f"Program: {self.program} - score: {self.score}"

    def __repr__(self) -> str:
        return self.__str__()


def individual_from_fitness(
    program: Genome,
    result: FitnessResult,
) -> Individual:
    return Individual(
        program,
        result.score,
        result.is_best,
        result.best_program,
        result.behavior,
    )


def winning_program(individual: Individual, rendered: ProgramText) -> ProgramText:
    return individual.best_program if individual.best_program is not None else rendered
