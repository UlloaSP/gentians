from typing import Any

from ..operator_types import SelectionFn
from .behavior_tournament_selection import BehaviorTournamentSelection
from .lexicase_selection import LexicaseSelection
from .tournament_selection import TournamentSelection


def create_selection(config: dict[str, Any]) -> SelectionFn:
    name = str(config["name"])
    if name == "tournament":
        percentage = config["tournament_percentage"]
        probability = config["prob_selecting_fittest"]
        if (
            not isinstance(percentage, (int, float))
            or isinstance(percentage, bool)
            or not isinstance(probability, (int, float))
            or isinstance(probability, bool)
        ):
            raise ValueError("tournament parameters must be numeric")
        return TournamentSelection(
            float(percentage),
            float(probability),
        )
    if name == "behavior_tournament":
        percentage = config["tournament_percentage"]
        if not isinstance(percentage, (int, float)) or isinstance(percentage, bool):
            raise ValueError("tournament_percentage must be numeric")
        return BehaviorTournamentSelection(float(percentage))
    if name == "lexicase":
        return LexicaseSelection()
    raise ValueError(f"Unknown selection strategy: {name}")
