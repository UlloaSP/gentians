from typing import Any

from ..operator_types import MutationFn
from .duplicate_group import DuplicateGroupMutation
from .per_clause import PerClauseMutation
from .random_group import RandomGroupMutation

MUTATIONS = {
    "random_group": RandomGroupMutation,
    "per_clause": PerClauseMutation,
    "duplicate_group": DuplicateGroupMutation,
}


def create_mutation(config: dict[str, Any]) -> MutationFn:
    name = str(config["name"])
    if name not in MUTATIONS:
        raise ValueError(f"Unknown mutation strategy: {name}")
    return MUTATIONS[name](
        config["probability"],
        config.get("random_jump_probability", 0.1),
        config.get("complete_generator_removal_probability", 0.1),
    )
