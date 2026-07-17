from dataclasses import dataclass, field
import time

from .types import Genome, ProgramText


@dataclass(slots=True)
class Individual:
    program: Genome
    score: float
    is_best: bool  # does this cover everything positive and no negative?
    best_program: ProgramText | None = None
    generated_timestamp: float = field(default_factory=time.time)

    def __str__(self) -> str:
        return f"Program: {self.program} - score: {self.score}"

    def __repr__(self) -> str:
        return self.__str__()


def individual_from_fitness(
    program: Genome,
    result: tuple[float, bool] | tuple[float, bool, ProgramText | None],
) -> Individual:
    score, is_best = result[0], result[1]
    best_program = result[2] if len(result) > 2 else None
    return Individual(program, score, is_best, best_program)


def winning_program(individual: Individual, rendered: ProgramText) -> ProgramText:
    return individual.best_program if individual.best_program is not None else rendered
