"""Epoch policies over complete hypotheses, independent of ASP predicates."""

import random
from collections.abc import Sequence

from ..evolution.individual import Individual
from ..evolution.reproduction import ReproductiveHistory
from ..hypotheses import Genome, HypothesisGenerator


def retain_population(
    population: list[Individual],
    champion: Individual,
    count: int,
    policy: str,
    history: ReproductiveHistory | None,
) -> list[Individual]:
    ranked = sorted(population, key=lambda item: item.score, reverse=True)
    if policy == "fitness":
        retained = ranked[:count]
        if champion not in retained:
            retained[-1] = champion
        return retained

    retained = [champion]
    remaining = [item for item in ranked if item.genome != champion.genome]
    while remaining and len(retained) < count:
        # Champion, then specialists; reproductive retention alternates specialists,
        # promising parents and parents with few observations.
        slot = (len(retained) - 1) % 3
        if policy == "reproductive" and history is not None and slot == 1:
            chosen = max(
                remaining, key=lambda item: (history.value(item.genome), item.score)
            )
        elif policy == "reproductive" and history is not None and slot == 2:
            chosen = min(
                remaining, key=lambda item: (history.attempts(item.genome), -item.score)
            )
        else:
            chosen = max(remaining, key=lambda item: _diversity(item, retained))
        retained.append(chosen)
        remaining.remove(chosen)
    return retained


def _diversity(
    item: Individual, retained: Sequence[Individual]
) -> tuple[int, int, float]:
    covered = 0
    shared_negatives = retained[0].behavior[1]
    for other in retained:
        covered |= other.behavior[0]
        shared_negatives &= other.behavior[1]
    gains = (item.behavior[0] & ~covered).bit_count()
    gains += (shared_negatives & ~item.behavior[1]).bit_count()
    distance = min(
        (item.behavior[0] ^ other.behavior[0]).bit_count()
        + (item.behavior[1] ^ other.behavior[1]).bit_count()
        for other in retained
    )
    return gains, distance, item.score


def build_clause_pool(
    hypotheses: HypothesisGenerator,
    seeds: Sequence[Genome],
    target: int,
    policy: str,
    rng: random.Random,
) -> Genome:
    hypotheses.set_pool(hypotheses.all_clauses)
    pool = 0
    for genome in seeds:
        pool |= genome
    target = min(target, hypotheses.clause_count)
    if policy == "neighbors" and seeds:
        # Aim for half the extra capacity locally; complete hypotheses may overshoot.
        local_target = pool.bit_count() + max(0, target - pool.bit_count()) // 2
        failures = 0
        while pool.bit_count() < local_target and failures < 256:
            parent = rng.choice(seeds)
            if parent.bit_count() < hypotheses.max_clauses and rng.random() < 0.5:
                candidate = hypotheses.append(parent, rng)
            else:
                candidate = hypotheses.replace(parent, rng, same_head=True)
            if candidate is None or candidate & ~pool == 0:
                failures += 1
            else:
                pool |= candidate
                failures = 0

    failures = 0
    while pool.bit_count() < target and failures < 256:
        candidate = hypotheses.create(rng)
        if candidate is None or candidate & ~pool == 0:
            failures += 1
            continue
        pool |= candidate
        failures = 0
    if not pool:
        candidate = hypotheses.create(rng)
        if candidate is None:
            raise RuntimeError("Could not construct an epoch pool")
        pool = candidate
    hypotheses.set_pool(pool)
    return pool
