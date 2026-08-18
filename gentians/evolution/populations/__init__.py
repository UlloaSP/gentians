from ..operator_types import PopulationInitializerFn
from .random_population import RandomPopulation


def create_population(config: dict[str, object]) -> PopulationInitializerFn:
    name = str(config["name"])
    strategies = {"random": RandomPopulation}
    try:
        strategy = strategies[name]
    except KeyError:
        raise ValueError(f"Unknown population strategy: {name}") from None
    return strategy(int(config["size"]))
