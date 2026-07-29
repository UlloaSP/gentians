from __future__ import annotations

from ..operator_types import SelectionFn
from .tournament_selection import TournamentSelection


def create_selection(config: dict[str, object]) -> SelectionFn:
    name = str(config["name"])
    if name == "tournament":
        return TournamentSelection(
            float(config["tournament_percentage"]),
            float(config["prob_selecting_fittest"]),
        )
    raise ValueError(f"Unknown selection strategy: {name}")
