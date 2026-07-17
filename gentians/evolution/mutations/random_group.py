from __future__ import annotations

from ..evolution_context import EvolutionContext
from ..operator_types import MutationProposal
from ..types import Genome


class RandomGroupMutation:
    def __init__(self, probability: float) -> None:
        self.probability = probability

    def __call__(self, genome: Genome, context: EvolutionContext) -> MutationProposal:
        if context.rng.random() >= self.probability:
            return MutationProposal(genome)
        operations = ["replace", "append", "remove"]
        context.rng.shuffle(operations)
        for operation in operations:
            candidate = self._apply(operation, genome, context)
            if candidate is not None:
                return MutationProposal(candidate, operation=operation, local=False)
        return MutationProposal(genome)

    @staticmethod
    def _apply(
        operation: str, genome: Genome, context: EvolutionContext
    ) -> Genome | None:
        if operation == "remove":
            rules = list(genome)
            context.rng.shuffle(rules)
            for rule in rules:
                if candidate := context.generator.remove(genome, rule):
                    return candidate
            return None
        available = [rule for rule in context.space.clauses if rule not in genome]
        context.rng.shuffle(available)
        if operation == "append":
            for rule in available:
                if candidate := context.generator.append(genome, rule):
                    return candidate
            return None
        sources = list(genome)
        context.rng.shuffle(sources)
        for source in sources:
            for replacement in available:
                if candidate := context.generator.replace(
                    genome, source, replacement
                ):
                    return candidate
        return None
