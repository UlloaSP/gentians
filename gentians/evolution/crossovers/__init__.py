from typing import Any

from ..operator_types import CrossoverFn
from .component_mix import ComponentMixCrossover
from .set_mix import SetMixCrossover


def create_crossover(config: dict[str, Any]) -> CrossoverFn:
    name = str(config["name"])
    strategies = {"set_mix": SetMixCrossover, "component_mix": ComponentMixCrossover}
    try:
        strategy = strategies[name]
    except KeyError:
        raise ValueError(f"Unknown crossover strategy: {name}") from None
    probability = config["probability"]
    if not isinstance(probability, (int, float)) or isinstance(probability, bool):
        raise ValueError("crossover probability must be a number between 0 and 1")
    return strategy(float(probability))
