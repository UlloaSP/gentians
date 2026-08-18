from ..operator_types import ReplacementFn
from .oldest_or_worst import OldestOrWorstReplacement


def create_replacement(config: dict[str, object]) -> ReplacementFn:
    name = str(config["name"])
    strategies = {"oldest_or_worst": OldestOrWorstReplacement}
    try:
        strategy = strategies[name]
    except KeyError:
        raise ValueError(f"Unknown replacement strategy: {name}") from None
    return strategy(
        float(config["prob_replacing_oldest"]),
        bool(config.get("behavior_tiebreak", False)),
    )
