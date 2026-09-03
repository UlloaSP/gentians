from typing import Any

from ..operator_types import ReplacementFn
from .oldest_or_worst import OldestOrWorstReplacement


def create_replacement(config: dict[str, Any]) -> ReplacementFn:
    name = str(config["name"])
    strategies = {"oldest_or_worst": OldestOrWorstReplacement}
    try:
        strategy = strategies[name]
    except KeyError:
        raise ValueError(f"Unknown replacement strategy: {name}") from None
    behavior_tiebreak = config.get("behavior_tiebreak", False)
    if not isinstance(behavior_tiebreak, bool):
        raise ValueError("behavior_tiebreak must be a boolean")
    probability = config["prob_replacing_oldest"]
    if not isinstance(probability, (int, float)) or isinstance(probability, bool):
        raise ValueError("replacement probability must be a number between 0 and 1")
    return strategy(float(probability), behavior_tiebreak)
