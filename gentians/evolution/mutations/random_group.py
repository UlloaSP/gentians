from ..evolution_context import EvolutionContext
from ..operator_types import MutationProposal
from ..types import Genome


class RandomGroupMutation:
    def __init__(self, probability: float) -> None:
        self.probability = probability

    def __call__(self, genome: Genome, context: EvolutionContext) -> MutationProposal:
        if context.rng.random() >= self.probability:
            return MutationProposal(genome, skipped=True)
        return context.hypotheses.mutate_random(genome)
