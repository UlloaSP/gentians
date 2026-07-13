from __future__ import annotations

from ..operator_types import CrossoverFn
from .set_mix import SetMixCrossover


def create_crossover(config: dict[str, object]) -> CrossoverFn:
    name = str(config["name"])
    strategies = {"set_mix": SetMixCrossover}
    try:
        strategy = strategies[name]
    except KeyError:
        raise ValueError(f"Unknown crossover strategy: {name}") from None
    return strategy(float(config["probability"]))
