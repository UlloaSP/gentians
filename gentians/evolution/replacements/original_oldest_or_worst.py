import random

from ..individual import Individual
from ...timing import instrumentation, metric_enabled, profile_phase, record_metric


@profile_phase("replacement")
def replace_original_oldest_or_worst(
    population: list[Individual],
    element: Individual,
    population_signatures: set[tuple[str, ...]],
    prob_replacing_oldest: float,
) -> list[Individual]:
    old_best_score = population[0].score if population else float("-inf")
    old_worst_score = population[-1].score if population else float("-inf")
    victim_score: float | str = ""
    accepted = False
    reject_reason = ""

    if element.program in population_signatures:
        reject_reason = "duplicate"
    else:
        insert_at = len(population)
        for index, current in enumerate(population):
            if element.score >= current.score:
                insert_at = index
                break
        population.insert(insert_at, element)
        population_signatures.add(element.program)
        if random.random() < prob_replacing_oldest:
            victim = min(population, key=lambda individual: individual.generated_timestamp)
        else:
            victim = population[-1]
        population.remove(victim)
        population_signatures.discard(victim.program)
        victim_score = victim.score
        accepted = victim is not element

    if metric_enabled("operator"):
        with instrumentation():
            record_metric(
                "operator",
                {
                    "operator": "replacement",
                    "strategy": "original_oldest_or_worst",
                    "slots": 1,
                    "accepted": accepted,
                    "duplicate": reject_reason == "duplicate",
                    "invalid": False,
                    "not_competitive": not accepted and not reject_reason,
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
