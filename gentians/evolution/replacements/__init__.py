from typing import Any

from ..operator_types import ReplacementFn
from .dominated_or_worst import DominatedOrWorstReplacement
from .genotypic_crowding import GenotypicCrowdingReplacement
from .oldest_or_worst import OldestOrWorstReplacement
from .phenotypic_crowding import PhenotypicCrowdingReplacement


def create_replacement(config: dict[str, Any]) -> ReplacementFn:
    name = str(config["name"])
    if name == "oldest_or_worst":
        probability = config["prob_replacing_oldest"]
        if not isinstance(probability, (int, float)) or isinstance(probability, bool):
            raise ValueError("replacement probability must be a number between 0 and 1")
        return OldestOrWorstReplacement(float(probability))
    if name == "dominated_or_worst":
        return DominatedOrWorstReplacement()
    # The crowding classes validate the factor; a float such as 2.0 is
    # rejected rather than truncated, because the factor counts individuals.
    if name == "genotypic_crowding":
        return GenotypicCrowdingReplacement(config["crowding_factor"])
    if name == "phenotypic_crowding":
        return PhenotypicCrowdingReplacement(config["crowding_factor"])
    raise ValueError(f"Unknown replacement strategy: {name}")
