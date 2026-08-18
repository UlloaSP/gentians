from ..operator_types import SelectionFn
from .behavior_tournament_selection import BehaviorTournamentSelection
from .tournament_selection import TournamentSelection


def create_selection(config: dict[str, object]) -> SelectionFn:
    name = str(config["name"])
    if name == "tournament":
        return TournamentSelection(
            float(config["tournament_percentage"]),
            float(config["prob_selecting_fittest"]),
        )
    if name == "behavior_tournament":
        return BehaviorTournamentSelection(float(config["tournament_percentage"]))
    raise ValueError(f"Unknown selection strategy: {name}")
