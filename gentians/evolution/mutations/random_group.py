from __future__ import annotations

from ..evolution_context import EvolutionContext
from ..types import Genome


class RandomGroupMutation:
    def __init__(self, probability: float) -> None:
        self.probability = probability

    def __call__(self, genome: Genome, context: EvolutionContext) -> Genome:
        if context.rng.random() >= self.probability:
            return genome
        candidate, current = list(genome), set(genome)
        available = [rule for rule in context.space.clauses if rule not in current]
        operations = []
        if candidate and available:
            operations.append("replace")
        if len(candidate) < context.max_program_clauses and available:
            operations.append("append")
        if len(candidate) > 1:
            operations.append("delete")
        if not operations:
            return genome
        operation = context.rng.choice(operations)
        if operation == "replace":
            candidate[context.rng.randrange(len(candidate))] = context.rng.choice(
                available
            )
        elif operation == "append":
            candidate.append(context.rng.choice(available))
        else:
            del candidate[context.rng.randrange(len(candidate))]
        return tuple(candidate)
