from collections.abc import Iterator
from dataclasses import dataclass

from .atom_literal import AtomLiteral
from .parser import Predicate
from .term_template import TermTemplate


@dataclass(frozen=True, slots=True)
class ConditionalLiteral:
    conclusion: AtomLiteral
    conditions: tuple[AtomLiteral, ...]
    condition_groups: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.conditions:
            raise ValueError("conditional literals require at least one condition")
        if len(self.conditions) != len(self.condition_groups):
            raise ValueError(
                "every conditional literal condition requires a recall group"
            )

    @property
    def kind(self) -> str:
        return "conditional"

    @property
    def arguments(self) -> tuple[TermTemplate, ...]:
        return (
            *self.conclusion.arguments,
            *(term for condition in self.conditions for term in condition.arguments),
        )

    @property
    def dependencies(self) -> frozenset[Predicate]:
        return frozenset(
            predicate
            for literal in (self.conclusion, *self.conditions)
            for predicate in literal.dependencies
        )

    def render(self, variables: Iterator[str]) -> str:
        conclusion = self.conclusion.render(variables)
        conditions = ",".join(
            condition.render(variables) for condition in self.conditions
        )
        return f"{conclusion}:{conditions}"
