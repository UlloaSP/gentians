import random

from ..individual import Individual
from ...timing import instrumentation, metric_enabled, profile_phase, record_metric


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
    ranked = sorted(
        random.sample(population, tournament_size),
        key=lambda individual: individual.score,
        reverse=True,
    )
    selected_index = 0
    while (
        selected_index < len(ranked) - 1
        and random.random() > prob_selecting_fittest
    ):
        selected_index += 1
    best_element = ranked[selected_index]

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
