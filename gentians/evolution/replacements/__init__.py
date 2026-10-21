from typing import Any

from ..operator_types import ReplacementFn
from .dominated_or_worst import DominatedOrWorstReplacement
from .oldest_or_worst import OldestOrWorstReplacement


def create_replacement(config: dict[str, Any]) -> ReplacementFn:
    name = str(config["name"])
    if name == "oldest_or_worst":
        probability = config["prob_replacing_oldest"]
        if not isinstance(probability, (int, float)) or isinstance(probability, bool):
            raise ValueError("replacement probability must be a number between 0 and 1")
        return OldestOrWorstReplacement(float(probability))
    if name == "dominated_or_worst":
        return DominatedOrWorstReplacement()
    raise ValueError(f"Unknown replacement strategy: {name}")
