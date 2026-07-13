from __future__ import annotations

from ..operator_types import MutationFn
from .random_group import RandomGroupMutation


def create_mutation(config: dict[str, object]) -> MutationFn:
    name = str(config["name"])
    strategies = {"random_group": RandomGroupMutation}
    try:
        strategy = strategies[name]
    except KeyError:
        raise ValueError(f"Unknown mutation strategy: {name}") from None
    return strategy(float(config["probability"]))
