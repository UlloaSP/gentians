from dataclasses import dataclass, field

from ..language.asp import Predicate
from ..language.ir.aggregate_literal import AggregateLiteral
from ..language.ir.arithmetic_literal import ArithmeticLiteral
from ..language.ir.atom_literal import AtomLiteral
from ..language.ir.comparison_literal import ComparisonLiteral
from ..language.ir.conditional_literal import ConditionalLiteral
from ..language.ir.head_template import HeadTemplate
from ..language.ir.head_aggregate_element import HeadAggregateElement
from ..language.ir.literal_template import LiteralTemplate
from ..language.ir.term_binding import TermBinding


@dataclass(frozen=True, slots=True)
class ClauseMode:
    id: int
    recall_group: int
    section: str
    recall: int
    literal: LiteralTemplate
    head_form: int | None = None
    head_position: int = 0
    head: HeadTemplate | None = None
    bindings: tuple[TermBinding, ...] = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if self.section not in {"head", "body"}:
            raise ValueError(f"invalid clause section: {self.section}")
        if self.section == "head":
            conclusion = (
                self.literal.conclusion
                if isinstance(self.literal, ConditionalLiteral)
                else AtomLiteral(self.literal.atom)
                if isinstance(self.literal, HeadAggregateElement)
                else self.literal
            )
            if not isinstance(conclusion, AtomLiteral) or conclusion.default_negated:
                raise ValueError("head modes require positive atom literals")
            if self.head_form is None or self.head is None:
                raise ValueError("head modes require a complete head form")
        elif self.head_form is not None or self.head is not None:
            raise ValueError("body modes cannot belong to a head form")
        object.__setattr__(
            self,
            "bindings",
            tuple(
                binding
                for index, term in enumerate(self.literal.arguments)
                for binding in term.bindings((index,))
            ),
        )

    @property
    def arity(self) -> int:
        return len(self.literal.arguments)

    @property
    def binding_positions(self) -> tuple[int, ...]:
        if isinstance(
            self.literal,
            AggregateLiteral | ConditionalLiteral | ComparisonLiteral | ArithmeticLiteral | HeadAggregateElement,
        ) or (
            isinstance(self.literal, AtomLiteral)
            and any(term.kind in {"function", "tuple"} for term in self.literal.atom.terms)
        ):
            return tuple(range(len(self.bindings)))
        return tuple(binding.path[0] for binding in self.bindings)

    @property
    def dependencies(self) -> frozenset[Predicate]:
        return self.literal.dependencies

    @property
    def condition_count(self) -> int:
        return (
            len(self.literal.conditions)
            if isinstance(self.literal, ConditionalLiteral | HeadAggregateElement)
            else 0
        )
