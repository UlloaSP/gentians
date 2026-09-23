from collections.abc import Iterator
from dataclasses import dataclass
from itertools import product

from ..asp import Predicate
from .aggregate_element import AggregateElement
from .aggregate_guard import AggregateGuard
from .atom_literal import AtomLiteral
from .term_template import TermTemplate


@dataclass(frozen=True, slots=True)
class AggregateLiteral:
    function: str
    elements: tuple[AggregateElement, ...]
    left_guard: AggregateGuard | None
    right_guard: AggregateGuard | None = None
    default_negated: bool = False
    double_negated: bool = False

    def __post_init__(self) -> None:
        if self.double_negated and not self.default_negated:
            raise ValueError("double negation requires default negation")

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
            dependency
            for element in self.elements
            for dependency in (
                *((element.conclusion.atom.signature,)
                  if isinstance(element.conclusion, AtomLiteral) else ()),
                *(item for condition in element.conditions for item in condition.dependencies),
            )
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
            AggregateLiteral(
                self.function, elements, left, right,
                self.default_negated, self.double_negated,
            )
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
        name = "" if self.function == "set" else f"#{self.function}"
        core = name + "{" + ";".join(
            element.render(variables) for element in self.elements
        ) + "}"
        if self.left_guard is not None:
            left = self.left_guard.term.render(variables)
            if self.left_guard.term.kind == "pool":
                left = f"({left})"
            core = (
                f"{core}={left}"
                if self.output_guard is not None
                else f"{left}{self.left_guard.operator}{core}"
            )
        if self.right_guard is not None:
            right = self.right_guard.term.render(variables)
            if self.right_guard.term.kind == "pool":
                right = f"({right})"
            core = f"{core}{self.right_guard.operator}{right}"
        if self.double_negated:
            return f"not not {core}"
        return f"not {core}" if self.default_negated else core
