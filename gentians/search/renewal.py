"""Epoch renewal and constraint probes of incremental clause search."""

from ..evolution.individual import Individual
from ..evolution.metrics import record_replacement
from ..hypotheses import Genome
from .clause_pool import IncrementalClausePool
from .population import Population


def renew_population(
    population: Population, pool: IncrementalClausePool, elite_count: int,
) -> None:
    """Move the elite into the next clause batch and refill around it."""
    retained = retain_population(
        population.members, population.best, min(elite_count, len(population.members)),
    )
    retained_mask = 0
    for item in retained:
        retained_mask |= item.genome
    candidates = population.candidates
    hypotheses = candidates.hypotheses
    entries = [hypotheses.space.entries[i] for i in hypotheses._ids(retained_mask)]
    proposed = pool.draw(entries)
    additions = 0
    if proposed is not None:
        retained, population.best, additions = candidates.renew(
            proposed, retained, population.best,
        )
    # Release the previous space before sampling the new one.
    del hypotheses, entries, proposed
    pool.activate(candidates.hypotheses, [item.genome for item in retained])
    population.members = population.fill(retained)
    probe_constraints(population, additions)
    if not population.members:
        raise RuntimeError("Could not refill population after batch renewal")
    population.remember_winner()


def probe_constraints(population: Population, additions: Genome) -> None:
    """Try up to 16 extensions of the best complete constraint-only program."""
    hypotheses = population.candidates.hypotheses
    if hypotheses.clauses_by_head or not hypotheses.has_positive_examples:
        return
    additions &= hypotheses.available_clauses
    complete = max((item for item in population.members if item.is_complete),
                   key=lambda item: item.score, default=None)
    rng = population.candidates.context.rng
    for _ in range(16):
        if population.winner is not None:
            break
        base = complete.genome if complete is not None else 0
        candidate = (
            hypotheses.replace(base, rng, mutable=base | additions)
            if base.bit_count() >= hypotheses.max_clauses
            else hypotheses.append(base, rng, mutable=additions)
        )
        if candidate is None:
            break
        child = population.candidates.admit(candidate)
        if child is None:
            continue
        if child.is_complete and (complete is None or child.score > complete.score):
            complete = child
        before = population.members
        population.members = population.replacement(population.members, child, rng)
        record_replacement(population.replacement_name, before, population.members, child)
        if child.is_solution:
            if child not in population.members:
                population.members[-1] = child
            break


def retain_population(
    population: list[Individual], champion: Individual, count: int,
) -> list[Individual]:
    retained = sorted(population, key=lambda item: item.score, reverse=True)[:count]
    if champion not in retained:
        retained[-1] = champion
    return retained
