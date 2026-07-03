import random

from ..individual import Individual
from ...timing import instrumentation, metric_enabled, profile_phase, record_metric


def get_fittest(selected_individuals: "list[Individual]") -> Individual:
    """
    Returns the fittest element in the current selection
    """
    return max(selected_individuals, key=lambda x: x.score)


@profile_phase("selection")
def tournament_selection(
    population: list[Individual],
    tournament_size: int,
    prob_selecting_fittest: float,
):
    """
    Tournament to select the individuals to combine and mutate
    """
    if not population:
        raise ValueError("Cannot select from an empty population")

    tournament_size = min(tournament_size, len(population))
    random_subset = random.sample(population, tournament_size)
    stop = False
    best_element = get_fittest(random_subset)
    while len(random_subset) > 1 and not stop:
        if random.random() > prob_selecting_fittest:
            random_subset.remove(best_element)
            best_element = get_fittest(random_subset)
        else:
            stop = True

    if metric_enabled("operator"):
        with instrumentation():
            record_metric(
                "operator",
                {
                    "operator": "selection",
                    "strategy": "tournament",
                    "population_size": len(population),
                    "tournament_size": tournament_size,
                    "selected_score": best_element.score,
                },
            )

    return best_element
