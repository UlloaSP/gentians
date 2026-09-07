import random

from ..individual import Individual
from ..reproduction import ReproductiveHistory
from .lexicase_selection import LexicaseSelection


class ReproductiveLexicaseSelection(LexicaseSelection):
    """Use offspring improvement rates to break ties after lexicase filtering."""

    def __init__(self, history: ReproductiveHistory) -> None:
        self.history = history

    def _choose(self, candidates: list[Individual], rng: random.Random) -> Individual:
        return rng.choices(
            candidates,
            weights=[self.history.value(item.genome) for item in candidates],
            k=1,
        )[0]
