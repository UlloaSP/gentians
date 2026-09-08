from typing import Any

from ..operator_types import MutationFn
from .random_group import RandomGroupMutation


def create_mutation(config: dict[str, Any]) -> MutationFn:
    name = str(config["name"])
    if name != "random_group":
        raise ValueError(f"Unknown mutation strategy: {name}")
    return RandomGroupMutation(
        config["probability"],
        config.get("random_jump_probability", 0.1),
        config.get("complete_generator_removal_probability", 0.1),
        config.get("completeness_guidance", True),
        config.get("constraint_only_random", False),
    )
