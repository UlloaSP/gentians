from typing import Any

from ..operator_types import SelectionFn
from .behavior_tournament_selection import BehaviorTournamentSelection
from .lexicase_selection import LexicaseSelection
from .tournament_selection import TournamentSelection


def create_selection(config: dict[str, Any]) -> SelectionFn:
    name = str(config["name"])
    if name == "tournament":
        return TournamentSelection(
            float(config["tournament_percentage"]),
            float(config["prob_selecting_fittest"]),
        )
    if name == "behavior_tournament":
        return BehaviorTournamentSelection(float(config["tournament_percentage"]))
    if name == "lexicase":
        return LexicaseSelection()
    raise ValueError(f"Unknown selection strategy: {name}")
