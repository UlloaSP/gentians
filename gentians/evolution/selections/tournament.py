import random

from ..individual import Individual


def get_fittest(selected_individuals: "list[Individual]") -> Individual:
    """
    Returns the fittest element in the current selection
    """
    return max(selected_individuals, key=lambda x: x.score)


def tournament_selection(
    population: list[Individual],
    tournament_size: int = 12,
    prob_selecting_fittest: float = 0.9,
):
    """
    Tournament to select the individuals to combine and mutate
    """
    random_subset = random.sample([x for x in population], tournament_size)
    stop = False
    best_element = get_fittest(random_subset)
    while len(random_subset) > 0 and not stop:
        if random.random() > prob_selecting_fittest:
            random_subset.remove(best_element)
            best_element = get_fittest(random_subset)
        else:
            stop = True

    return best_element
