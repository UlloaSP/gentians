import math
import random

from ..individual import Individual
from ...timing import instrumentation, metric_enabled, profile_phase, record_metric


@profile_phase("replacement")
def replace_oldest_or_worst(
    population: list[Individual],
    element: Individual,
    population_signatures: set[tuple[str, ...]],
    prob_replacing_oldest: float,
) -> list[Individual]:
    accepted = False
    reject_reason = ""
    old_best_score = population[0].score if population else float("-inf")
    old_worst_score = population[-1].score if population else float("-inf")
    victim_score = ""
    if element.program in population_signatures:
        reject_reason = "duplicate"
    elif not math.isfinite(element.score):
        reject_reason = "non_finite"
    elif not population:
        population.append(element)
        population_signatures.add(element.program)
        accepted = True
    elif element.score < population[-1].score:
        reject_reason = "not_competitive"
    else:
        victim_index = len(population) - 1
        if random.random() < prob_replacing_oldest:
            oldest_index = min(
                range(len(population)),
                key=lambda index: population[index].generated_timestamp,
            )
            if element.score >= population[oldest_index].score:
                victim_index = oldest_index

        victim = population.pop(victim_index)
        population_signatures.discard(victim.program)
        insert_at = len(population)
        for index, current in enumerate(population):
            if element.score >= current.score:
                insert_at = index
                break
        population.insert(insert_at, element)
        population_signatures.add(element.program)
        victim_score = victim.score
        accepted = True

    if metric_enabled("operator"):
        with instrumentation():
            record_metric(
                "operator",
                {
                    "operator": "replacement",
                    "strategy": "oldest_or_worst",
                    "slots": 1,
                    "accepted": accepted,
                    "duplicate": reject_reason == "duplicate",
                    "invalid": reject_reason == "non_finite",
                    "not_competitive": reject_reason == "not_competitive",
                    "improved": accepted and element.score > old_best_score,
                    "improved_victim": (
                        accepted
                        and victim_score != ""
                        and element.score > float(victim_score)
                    ),
                    "reject_reason": reject_reason,
                    "candidate_score": element.score,
                    "old_best_score": old_best_score,
                    "old_worst_score": old_worst_score,
                    "victim_score": victim_score,
                    "population_size": len(population),
                },
            )

    return population
