from ..context import EvolutionContext
from ..operator_types import MutationProposal
from ...hypotheses import Genome
from .random_group import RandomGroupMutation


class PerClauseMutation(RandomGroupMutation):
    """Give each clause of a duplicate crossover its own `random_group` edit.

    Only a forced call mutates: a crossover child not yet evaluated is kept as
    is. A forced call draws `probability` once per clause, not once per
    offspring; with no drawn clause it is skipped. Each drawn clause receives
    one append, remove or replace targeted at it, with the same permissions as
    `random_group`. The offspring's evaluation guides every edit: the
    intermediate programs are not evaluated, so the guards are a heuristic
    after the first edit.
    """

    def __call__(
        self,
        genome: Genome,
        context: EvolutionContext,
        force: bool = False,
    ) -> MutationProposal:
        if not force:
            return MutationProposal(genome, skipped=True)
        rng = context.rng
        drawn = [clause_id for clause_id in range(genome.bit_length())
                 if genome >> clause_id & 1 and rng.random() < self.probability]
        if not drawn:
            return MutationProposal(genome, skipped=True)
        result, solved = self._classify(genome, context)
        if solved:
            return MutationProposal(genome, skipped=True)
        rng.shuffle(drawn)
        candidate, operations = genome, []
        for clause_id in drawn:
            clause = 1 << clause_id
            if not candidate & clause:
                # An earlier edit removed it with its dependency block.
                continue
            proposal = self._propose(
                candidate, context, result, self._remove_headed(candidate, context, result), sources=clause,
            )
            if proposal.operation is not None:
                candidate = proposal.genome
                operations.append(proposal.operation)
        return MutationProposal(candidate, operation="+".join(operations) or None)
