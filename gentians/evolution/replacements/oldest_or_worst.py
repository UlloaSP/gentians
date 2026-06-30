import math
import random

from ..individual import Individual
from ...rule_generation.rule_space import RuleId
from ...timing import profile_phase, record_metric


@profile_phase("replacement")
def replace_oldest_or_worst(
    population: list[Individual],
    element: Individual,
    population_signatures: set[tuple[RuleId, ...]],
    prob_replacing_oldest: float,
) -> list[Individual]:
    accepted = False
    reject_reason = ""
    if element.signature in population_signatures:
        reject_reason = "duplicate"
    elif not math.isfinite(element.score):
        reject_reason = "non_finite"
    elif not population:
        population.append(element)
        population_signatures.add(element.signature)
        accepted = True
    else:
        replace_oldest = random.random() < prob_replacing_oldest
        if not replace_oldest and element.score < population[-1].score:
            reject_reason = "not_competitive"
        else:
            insert_at = len(population)
            for index, current in enumerate(population):
                if element.score >= current.score:
                    insert_at = index
                    break
            population.insert(insert_at, element)
            population_signatures.add(element.signature)

            if replace_oldest:
                victim = min(
                    (current for current in population if current is not element),
                    key=lambda x: x.generated_timestamp,
                )
                population.remove(victim)
            else:
                victim = population.pop()
            population_signatures.discard(victim.signature)
            accepted = True

    record_metric(
        "operator",
        {
            "operator": "replacement",
            "strategy": "oldest_or_worst",
            "accepted": accepted,
            "duplicate": reject_reason == "duplicate",
            "reject_reason": reject_reason,
            "candidate_score": element.score,
            "population_size": len(population),
        },
    )

    return population
