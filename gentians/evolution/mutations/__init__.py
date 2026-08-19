from typing import Any

from ..operator_types import MutationFn
from .random_group import RandomGroupMutation
from .structural_neighbor import StructuralNeighborMutation


def create_mutation(config: dict[str, Any]) -> MutationFn:
    name = str(config["name"])
    probability = float(config["probability"])
    if name == "random_group":
        return RandomGroupMutation(probability)
    if name == "structural_neighbor":
        return StructuralNeighborMutation(
            probability,
            float(config.get("random_jump_probability", 0.1)),
        )
    raise ValueError(f"Unknown mutation strategy: {name}")
