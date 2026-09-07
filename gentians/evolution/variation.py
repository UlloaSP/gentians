"""Shared search preferences; genotype legality stays in HypothesisGenerator."""

from .context import EvolutionContext
from ..evaluation.result import EvaluationResult
from ..hypotheses import Genome


def _result(
    genome: Genome, context: EvolutionContext, *, classify: bool = False,
) -> EvaluationResult | None:
    if context.results is not None and genome in context.results:
        return context.results[genome]
    h = context.hypotheses
    # Mutation needs the actual child's state even in homogeneous spaces.
    # Crossover retains its mixed-space classification policy.
    if (context.evaluate is not None and h.has_positive_examples
            and (classify or (h.has_negative_examples
                 and h.available_clauses & h.constraint_clauses
                 and h.available_clauses & ~h.constraint_clauses))):
        return context.evaluate(genome)
    return None


def _prefer_constraints(result: EvaluationResult | None, context: EvolutionContext) -> bool:
    h = context.hypotheses
    return bool(
        result is not None and result.is_complete and h.has_positive_examples
        and h.available_clauses & h.constraint_clauses
        and h.available_clauses & ~h.constraint_clauses
        # A complete generator need not be repairable by learnable constraints.
        and context.rng.random() >= 0.1
    )


def cross(first: Genome, second: Genome, context: EvolutionContext) -> Genome | None:
    first_result, second_result = _result(first, context), _result(second, context)
    if first_result is not None and first_result.is_solution:
        return first
    if second_result is not None and second_result.is_solution:
        return second
    probabilities = context.rng.choice(((0.7, 0.3), (0.3, 0.7)))
    recipient, donor, result = first, second, first_result
    if (second_result is not None and second_result.is_complete
            and (first_result is None or not first_result.is_complete)):
        recipient, donor, result = second, first, second_result
    if _prefer_constraints(result, context):
        child = context.hypotheses.mix_constraints(
            recipient, donor, probabilities, context.rng,
        )
        if child is not None and child != recipient:
            return child
    return context.hypotheses.mix(first, second, probabilities, context.rng)
