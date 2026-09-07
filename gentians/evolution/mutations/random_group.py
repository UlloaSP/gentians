from ..context import EvolutionContext
from ..operator_types import MutationProposal
from ...hypotheses import Genome
from ...evaluation.result import EvaluationResult
from ..variation import _result


class RandomGroupMutation:
    """Add, replace or remove one root clause and its dependency block."""

    def __init__(
        self, probability: float, random_jump_probability: float = 0.1,
        complete_generator_removal_probability: float = 0.1,
        duplicate_retries: int = 0,
    ) -> None:
        for name, value in (
            ("mutation probability", probability),
            ("random_jump_probability", random_jump_probability),
            ("complete_generator_removal_probability", complete_generator_removal_probability),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be a number between 0 and 1")
        self.probability = probability
        self.random_jump_probability = random_jump_probability
        self.complete_generator_removal_probability = complete_generator_removal_probability
        if type(duplicate_retries) is not int or duplicate_retries < 0:
            raise ValueError("duplicate_retries must be a non-negative integer")
        self.duplicate_retries = duplicate_retries

    def __call__(self, genome: Genome, context: EvolutionContext) -> MutationProposal:
        if context.rng.random() >= self.probability:
            return MutationProposal(genome, skipped=True)
        result = _result(genome, context, classify=True)
        if result is not None and result.is_solution:
            return MutationProposal(genome, skipped=True)
        h = context.hypotheses
        remove_headed = bool(
            result is not None and result.is_complete and h.has_positive_examples
            and genome & h.available_clauses & ~h.constraint_clauses
            and context.rng.random() < self.complete_generator_removal_probability
        )
        for _ in range(self.duplicate_retries + 1):
            proposal = self._propose(genome, context, result, remove_headed)
            if (proposal.skipped or context.seen is None
                    or proposal.genome not in context.seen):
                return proposal
        return proposal

    def _propose(
        self, genome: Genome, context: EvolutionContext,
        result: EvaluationResult | None, remove_headed: bool,
    ) -> MutationProposal:
        # Retry from the same input. The probability gate is drawn only once;
        # cached admission history avoids evaluating discarded proposals.
        h, rng = context.hypotheses, context.rng
        headed = h.available_clauses & ~h.constraint_clauses
        complete = bool(result is not None and result.is_complete and h.has_positive_examples)
        incomplete = bool(result is not None and not result.is_complete and h.has_positive_examples)

        if complete:
            # One draw per mutation decision, not per failed clause proposal.
            # This is an attempt at simplification, never proof of redundancy.
            if remove_headed:
                candidate = h.remove(genome, rng, sources=headed)
                if candidate is not None and candidate != genome:
                    return MutationProposal(candidate, operation="remove")
            mutable = h.constraint_clauses
        else:
            mutable = h.available_clauses
        if not h.has_negative_examples:
            # Existing constraints may be deleted, including normalization when
            # a constraint-only candidate first acquires a headed clause.
            mutable &= ~h.constraint_clauses | genome

        operations = h.operations(genome)
        rng.shuffle(operations)
        for operation in operations:
            local = None
            if operation == "append":
                # Pure constraints cannot recover a missing brave witness.
                additions = mutable & (headed | genome) if incomplete else mutable
                candidate = h.append(genome, rng, mutable=additions)
            elif operation == "remove":
                candidate = h.remove(genome, rng, mutable=mutable)
            else:
                local = rng.random() >= self.random_jump_probability
                candidate = h.replace(genome, rng, same_head=local, mutable=mutable,
                                      same_kind=incomplete and h.has_negative_examples)
            if candidate is not None and candidate != genome:
                return MutationProposal(candidate, operation=operation, local=local)
        # Complete generators are protected even if every constraint edit fails.
        return MutationProposal(genome)
