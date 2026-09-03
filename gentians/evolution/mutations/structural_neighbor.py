from ..evolution_context import EvolutionContext
from ..operator_types import MutationProposal
from ...hypotheses import Genome


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
        operations = context.hypotheses.operations(genome)
        context.rng.shuffle(operations)
        for operation in operations:
            if operation == "replace":
                random_jump = context.rng.random() < self.random_jump_probability
                candidate = context.hypotheses.replace(
                    genome, context.rng, same_head=not random_jump
                )
                local = not random_jump
            elif operation == "append":
                candidate = context.hypotheses.append(genome, context.rng)
                local = False
            else:
                candidate = context.hypotheses.remove(genome, context.rng)
                local = False
            if candidate is not None:
                return MutationProposal(candidate, operation=operation, local=local)
        return MutationProposal(genome)
