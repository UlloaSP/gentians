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

    def __call__(
        self,
        genome: Genome,
        context: EvolutionContext,
        force: bool = False,
    ) -> MutationProposal:
        # A duplicate crossover contains no new genetic material. The search
        # forces mutation in that case; otherwise the configured gate applies.
        if not force and context.rng.random() >= self.probability:
            return MutationProposal(genome, skipped=True)
        h = context.hypotheses
        headed = h.available_clauses & ~h.constraint_clauses
        random_constraints = not headed
        if random_constraints:
            result = context.results.get(genome) if context.results is not None else None
        else:
            result = _result(genome, context, classify=True)
        if result is not None and result.is_solution:
            return MutationProposal(genome, skipped=True)
        if random_constraints:
            result = None
        remove_headed = bool(
            result is not None and result.is_complete and h.has_positive_examples
            and genome & h.available_clauses & ~h.constraint_clauses
            and context.rng.random() < self.complete_generator_removal_probability
        )
        return self._propose(genome, context, result, remove_headed)

    def _propose(
        self, genome: Genome, context: EvolutionContext,
        result: EvaluationResult | None, remove_headed: bool,
    ) -> MutationProposal:
        h, rng = context.hypotheses, context.rng
        headed = h.available_clauses & ~h.constraint_clauses
        # Search policy, not semantic pruning: constraint additions may
        # improve negative coverage even when positive coverage is incomplete.
        random_constraints = not headed
        complete = bool(result is not None and result.is_complete and h.has_positive_examples)
        incomplete = bool(result is not None and not result.is_complete and h.has_positive_examples)

        if complete and h.available_clauses & h.constraint_clauses:
            # Completeness alone cannot freeze headed rules when the active
            # space has no constraints with which to remove negative witnesses.
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
                local = not random_constraints and rng.random() >= self.random_jump_probability
                candidate = h.replace(genome, rng, same_head=local, mutable=mutable,
                                      same_kind=incomplete and h.has_negative_examples)
            if candidate is not None and candidate != genome:
                return MutationProposal(candidate, operation=operation, local=local)
        # In mixed spaces, complete generators remain protected if edits fail.
        return MutationProposal(genome)
