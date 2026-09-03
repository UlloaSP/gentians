from ..context import EvolutionContext
from ..operator_types import MutationProposal
from ...hypotheses import Genome


class RandomGroupMutation:
    def __init__(self, probability: float) -> None:
        self.probability = probability

    def __call__(self, genome: Genome, context: EvolutionContext) -> MutationProposal:
        if context.rng.random() >= self.probability:
            return MutationProposal(genome, skipped=True)
        operations = context.hypotheses.operations(genome)
        context.rng.shuffle(operations)
        for operation in operations:
            if operation == "append":
                candidate = context.hypotheses.append(genome, context.rng)
            elif operation == "remove":
                candidate = context.hypotheses.remove(genome, context.rng)
            else:
                candidate = context.hypotheses.replace(genome, context.rng)
            if candidate is not None:
                return MutationProposal(candidate, operation=operation, local=False)
        return MutationProposal(genome)
