from ..context import EvolutionContext
from ..operator_types import MutationProposal
from ...hypotheses import Genome
from .random_group import RandomGroupMutation


class DuplicateGroupMutation(RandomGroupMutation):
    """Apply one `random_group` edit only to a duplicate crossover.

    A crossover child not yet evaluated is kept as is. A duplicate always
    mutates, exactly as in `random_group`; `probability` is ignored.
    """

    def __call__(
        self,
        genome: Genome,
        context: EvolutionContext,
        force: bool = False,
    ) -> MutationProposal:
        if not force:
            return MutationProposal(genome, skipped=True)
        result, solved = self._classify(genome, context)
        if solved:
            return MutationProposal(genome, skipped=True)
        return self._propose(genome, context, result, self._remove_headed(genome, context, result))
