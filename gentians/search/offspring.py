"""One mating event, including phase attribution of candidate evaluation."""

from ..evolution.individual import Individual
from ..evolution.metrics import (
    record_crossover, record_mutation, record_selection, record_skipped_crossover,
)
from ..evolution.operator_types import CrossoverFn, MutationFn, SelectionFn
from ..timing import phase
from .population import Population


def create_offspring(
    population: Population,
    selection: SelectionFn, crossover: CrossoverFn, mutation: MutationFn,
    names: tuple[str, str, str],
) -> tuple[Individual | None, bool]:
    """Return the admitted child and whether the final genome was a duplicate."""
    candidates = population.candidates
    context = candidates.context
    selection_name, crossover_name, mutation_name = names
    with phase("selection"):
        first, second = selection(population.members, 2, context.rng)
        record_selection(selection_name, first, second, len(population.members))
    with phase("crossover"):
        crossed = crossover(first.genome, second.genome, context)
    if crossed is None:
        record_skipped_crossover(crossover_name, len(population.members))
        return None, False
    best_parent = first if first.score >= second.score else second
    crossed_duplicate = crossed in candidates.evaluated
    with phase("mutation"):
        proposal = mutation(crossed, context, crossed_duplicate)
    final_genome = proposal.genome
    changed = final_genome != crossed
    duplicate = final_genome in candidates.evaluated
    with phase("mutation" if changed else "crossover"):
        child = None if duplicate else candidates.admit(final_genome)
    # Recorded after mutation, whose classification may have scored the crossover child.
    crossed_result = candidates.results.get(crossed)
    record_crossover(
        crossover_name, best_parent, crossed, duplicate=crossed_duplicate, result=crossed_result,
    )
    record_mutation(
        mutation_name, crossed, proposal, duplicate=changed and duplicate,
        before=crossed_result, after=candidates.results.get(final_genome),
        crossover_strategy=crossover_name, crossover_parent_score=best_parent.score,
    )
    return child, duplicate
