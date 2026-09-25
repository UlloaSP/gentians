from typing import Any

from ..operator_types import RestartFn
from .stagnation_restart import StagnationRestart


def create_restart(config: dict[str, Any]) -> RestartFn:
    name = str(config["name"])
    strategies = {"stagnation": StagnationRestart}
    try:
        strategy = strategies[name]
    except KeyError:
        raise ValueError(f"Unknown restart strategy: {name}") from None
    return strategy(config["generations"])
