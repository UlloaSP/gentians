from dataclasses import dataclass

from .atom_literal import AtomLiteral
from .conditional_literal import ConditionalLiteral
from .head_template import HeadTemplate
from .literal_template import LiteralTemplate
from .parser import Predicate
from .term_binding import TermBinding


@dataclass(frozen=True, slots=True)
class HypothesisMode:
    id: int
    recall_group: int
    section: str
    recall: int
    literal: LiteralTemplate
    head_form: int | None = None
    head_position: int = 0
    head: HeadTemplate | None = None
    aggregate_head: bool = False

    def __post_init__(self) -> None:
        if self.section not in {"head", "body"}:
            raise ValueError(f"invalid hypothesis section: {self.section}")
        if self.section == "head":
            conclusion = (
                self.literal.conclusion
                if isinstance(self.literal, ConditionalLiteral)
                else self.literal
            )
            if not isinstance(conclusion, AtomLiteral) or conclusion.default_negated:
                raise ValueError("head modes require positive atom literals")
            if self.head_form is None or self.head is None:
                raise ValueError("head modes require a complete head form")
            if self.aggregate_head and self.head.kind != "choice":
                raise ValueError("aggregate head modes require a choice head")
        elif self.head_form is not None or self.head is not None or self.aggregate_head:
            raise ValueError("body modes cannot belong to a head form")

    @property
    def arity(self) -> int:
        return len(self.literal.arguments)

    @property
    def bindings(self) -> tuple[TermBinding, ...]:
        return tuple(
            binding
            for index, term in enumerate(self.literal.arguments)
            for binding in term.bindings((index,))
        )

    @property
    def dependencies(self) -> frozenset[Predicate]:
        return self.literal.dependencies

    @property
    def condition_count(self) -> int:
        return (
            len(self.literal.conditions)
            if isinstance(self.literal, ConditionalLiteral)
            else 0
        )
