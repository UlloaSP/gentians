from ..evolution_context import EvolutionContext
from ..operator_types import MutationProposal
from ..types import Genome


class StructuralNeighborMutation:
    def __init__(
        self,
        probability: float,
        random_jump_probability: float,
    ) -> None:
        if not 0.0 <= random_jump_probability <= 1.0:
            raise ValueError("random_jump_probability must be between 0 and 1")
        self.probability = probability
        self.random_jump_probability = random_jump_probability

    def __call__(self, genome: Genome, context: EvolutionContext) -> MutationProposal:
        if context.rng.random() >= self.probability:
            return MutationProposal(genome, skipped=True)
        return context.generator.mutate_structural(
            genome, self.random_jump_probability
        )
