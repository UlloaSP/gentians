from typing import Any

from ..operator_types import MutationFn
from .random_group import RandomGroupMutation
from .structural_neighbor import StructuralNeighborMutation


def create_mutation(config: dict[str, Any]) -> MutationFn:
    name = str(config["name"])
    if name not in {"random_group", "structural_neighbor"}:
        raise ValueError(f"Unknown mutation strategy: {name}")
    configured_probability = config["probability"]
    if not isinstance(configured_probability, (int, float)) or isinstance(
        configured_probability, bool
    ):
        raise ValueError("mutation probability must be a number between 0 and 1")
    probability = float(configured_probability)
    if name == "random_group":
        return RandomGroupMutation(probability)
    configured_jump = config.get("random_jump_probability", 0.1)
    if not isinstance(configured_jump, (int, float)) or isinstance(
        configured_jump, bool
    ):
        raise ValueError("random_jump_probability must be a number between 0 and 1")
    return StructuralNeighborMutation(
        probability,
        float(configured_jump),
    )
