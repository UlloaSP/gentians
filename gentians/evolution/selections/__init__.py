from typing import Any

from ..operator_types import SelectionFn
from ..reproduction import ReproductiveHistory
from .behavior_tournament_selection import BehaviorTournamentSelection
from .lexicase_selection import LexicaseSelection
from .reproductive_lexicase_selection import ReproductiveLexicaseSelection
from .tournament_selection import TournamentSelection


def create_selection(
    config: dict[str, Any], history: ReproductiveHistory | None = None
) -> SelectionFn:
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
    if name == "reproductive_lexicase":
        if history is None:
            raise ValueError("reproductive_lexicase requires shared reproductive history")
        return ReproductiveLexicaseSelection(history)
    raise ValueError(f"Unknown selection strategy: {name}")
