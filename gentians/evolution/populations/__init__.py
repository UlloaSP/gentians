from typing import Any

from ..operator_types import PopulationInitializerFn
from .random_population import RandomPopulation


def create_population(config: dict[str, Any]) -> PopulationInitializerFn:
    name = str(config["name"])
    strategies = {"random": RandomPopulation}
    try:
        strategy = strategies[name]
    except KeyError:
        raise ValueError(f"Unknown population strategy: {name}") from None
    size = config["size"]
    if not isinstance(size, int) or isinstance(size, bool):
        raise ValueError("population size must be a positive integer")
    return strategy(size)
