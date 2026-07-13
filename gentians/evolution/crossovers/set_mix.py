from __future__ import annotations

from ..evolution_context import EvolutionContext
from ..types import Genome


class SetMixCrossover:
    def __init__(self, probability: float) -> None:
        self.probability = probability

    def __call__(
        self, first: Genome, second: Genome, context: EvolutionContext
    ) -> tuple[Genome, ...]:
        if context.rng.random() >= self.probability:
            return ()
        common = set(first) & set(second)
        only_first = set(first) - set(second)
        only_second = set(second) - set(first)
        return (
            self._child(common, only_first, only_second, 0.7, 0.3, context),
            self._child(common, only_first, only_second, 0.3, 0.7, context),
        )

    @staticmethod
    def _child(
        common: set[str],
        only_first: set[str],
        only_second: set[str],
        first_probability: float,
        second_probability: float,
        context: EvolutionContext,
    ) -> Genome:
        selected = set(common)
        selected.update(
            rule for rule in only_first if context.rng.random() < first_probability
        )
        selected.update(
            rule for rule in only_second if context.rng.random() < second_probability
        )
        if not selected:
            selected.add(context.rng.choice(tuple(only_first | only_second)))
        if len(selected) > context.max_program_clauses:
            selected = set(
                context.rng.sample(tuple(selected), context.max_program_clauses)
            )
        return tuple(sorted(selected))
