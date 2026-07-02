import random

from ..individual import Individual
from ...timing import profile_phase, record_metric


@profile_phase("selection")
def pick_two_fittest(
    population: list[Individual], pick_uniform: bool
) -> tuple[Individual, Individual]:
    """
    Pick the two fittest elements.
    If pick_uniform is true, select a random element between the ones with
    the highest fit (since most programs have the same fitness).
    """
    if not population:
        raise ValueError("Cannot select from an empty population")
    if len(population) == 1:
        return population[0], population[0]

    max_score = population[0].score
    i = 1
    j = 1
    for i in range(1, len(population)):
        if population[i].score < max_score:
            break

    if i < 2:
        max_score = population[i].score
        for j in range(i, len(population)):
            if population[j].score < max_score:
                break
    else:
        j = i

    # 2.1: pick the two fittest
    if not pick_uniform:
        # this is the naive version. However, since many programs have the same
        # score, # i should choose a random one among these
        best_a = population[0]
        best_b = population[1]
    else:
        idx_a, idx_b = random.sample(range(0, j), 2)
        best_a = population[idx_a]
        best_b = population[idx_b]

    record_metric(
        "operator",
        {
            "operator": "selection",
            "strategy": "pick_two_fittest",
            "population_size": len(population),
            "selected_a_score": best_a.score,
            "selected_b_score": best_b.score,
        },
    )

    return best_a, best_b
