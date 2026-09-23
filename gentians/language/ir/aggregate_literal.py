from collections.abc import Iterator
from dataclasses import dataclass
from itertools import product

from ..asp import Predicate
from .aggregate_element import AggregateElement
from .aggregate_guard import AggregateGuard
from .term_template import TermTemplate


@dataclass(frozen=True, slots=True)
class AggregateLiteral:
    function: str
    elements: tuple[AggregateElement, ...]
    left_guard: AggregateGuard | None
    right_guard: AggregateGuard | None = None

    @property
    def kind(self) -> str:
        return "aggregate"

    @property
    def arguments(self) -> tuple[TermTemplate, ...]:
        return (
            *(term for element in self.elements for term in element.arguments),
            *((self.left_guard.term,) if self.left_guard else ()),
            *((self.right_guard.term,) if self.right_guard else ()),
        )

    @property
    def dependencies(self) -> frozenset[Predicate]:
        return frozenset(
            atom.signature for element in self.elements for atom in element.conditions
        )

    @property
    def output_guard(self) -> AggregateGuard | None:
        if (
            self.left_guard is not None
            and self.left_guard.operator == "="
            and self.right_guard is None
            and self.left_guard.term.kind == "variable"
            and self.left_guard.term.direction == "output"
        ):
            return self.left_guard
        return None

    def concretizations(
        self, constants: dict[str, tuple[str, ...]]
    ) -> tuple["AggregateLiteral", ...]:
        return tuple(
            AggregateLiteral(self.function, elements, left, right)
            for elements in product(
                *(element.concretizations(constants) for element in self.elements)
            )
            for left in (
                self.left_guard.concretizations(constants)
                if self.left_guard is not None else (None,)
            )
            for right in (
                self.right_guard.concretizations(constants)
                if self.right_guard is not None else (None,)
            )
        )

    def render(self, variables: Iterator[str]) -> str:
        core = f"#{self.function}" + "{" + ";".join(
            element.render(variables) for element in self.elements
        ) + "}"
        if self.left_guard is not None:
            left = self.left_guard.term.render(variables)
            core = (
                f"{core}={left}"
                if self.output_guard is not None
                else f"{left}{self.left_guard.operator}{core}"
            )
        if self.right_guard is not None:
            core = f"{core}{self.right_guard.operator}{self.right_guard.term.render(variables)}"
        return core
