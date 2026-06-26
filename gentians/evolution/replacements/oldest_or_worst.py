import random

from ..individual import Individual
from ...timing import record_metric


def replace_oldest_or_worst(
    population: list[Individual],
    element: Individual,
    prob_replacing_oldest: float,
) -> list[Individual]:
    found = False
    # if not best, check whether it is already in the population
    for pop in population:
        if pop.signature == element.signature:
            found = True
            break

    # if not in the population, insert
    if not found:
        i = 0
        for i, current in enumerate(population):
            # equal to have some variability?
            if element.score >= current.score:
                break
        population.insert(i, element)

        # drop the element
        if random.random() < prob_replacing_oldest:
            # drop the oldest element
            oldest = min(population, key=lambda x: x.generated_timestamp)
            population.remove(oldest)
        else:
            # drop the element with the lowest fitness
            population = population[:-1]

    record_metric(
        "operator",
        {
            "operator": "replacement",
            "strategy": "oldest_or_worst",
            "accepted": not found,
            "duplicate": found,
            "candidate_score": element.score,
            "population_size": len(population),
        },
    )

    return population
