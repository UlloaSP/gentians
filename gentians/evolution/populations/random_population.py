from ..context import EvolutionContext
from ...hypotheses import Genome


class RandomPopulation:
    def __init__(self, size: int) -> None:
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            raise ValueError("population size must be a positive integer")
        self.size = size

    def __call__(self, context: EvolutionContext) -> list[Genome]:
        population: list[Genome] = []
        seen: set[Genome] = set()
        failed_attempts = 0
        while len(population) < self.size and failed_attempts < 64:
            candidate = context.hypotheses.create(context.rng)
            if candidate is not None and candidate not in seen:
                population.append(candidate)
                seen.add(candidate)
                failed_attempts = 0
            else:
                failed_attempts += 1
        return population
