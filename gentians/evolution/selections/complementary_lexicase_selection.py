import random

from ..individual import Individual
from .lexicase_selection import LexicaseSelection


class ComplementaryLexicaseSelection(LexicaseSelection):
    """Lexicase whose later parents first face the cases earlier ones fail.

    The first parent is chosen by ordinary lexicase. Each later parent sees, in
    random order, the cases every parent already selected fails: positives none
    of them covers and negatives all of them cover. The remaining cases follow,
    also shuffled. This is a search preference for complementary parents, not
    a prediction of the child's coverage: combining programs does not combine
    their coverage under stable-model semantics.
    """

    @staticmethod
    def _order(
        cases: tuple[tuple[int, bool], ...],
        selected: list[Individual],
        rng: random.Random,
    ) -> list[tuple[int, bool]]:
        shuffled_cases = LexicaseSelection._order(cases, selected, rng)
        if not selected:
            return shuffled_cases
        index = {True: 0, False: 1}
        failed = [
            case for case in shuffled_cases
            if all(bool(parent.behavior[index[case[1]]] & case[0]) != case[1] for parent in selected)
        ]
        return failed + [case for case in shuffled_cases if case not in failed]
