from dataclasses import dataclass, field

from clingo import ast

from ..language import terms as mode_terms
from ..language.asp import Predicate
from ..language.ir.aggregate_literal import AggregateLiteral
from ..language.ir.arithmetic_literal import ArithmeticLiteral
from ..language.ir.atom_literal import AtomLiteral
from ..language.ir.boolean_literal import BooleanLiteral
from ..language.ir.comparison_literal import ComparisonLiteral
from ..language.ir.conditional_literal import ConditionalLiteral
from ..language.ir.head_aggregate_element import HeadAggregateElement
from ..language.ir.head_template import HeadTemplate
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
    # Derived once: canonicalization reads it for every literal of every clause.
    dependencies: frozenset[Predicate] = field(
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
                if isinstance(self.literal, ConditionalLiteral | HeadAggregateElement)
                else self.literal
            )
            if not isinstance(conclusion, AtomLiteral | BooleanLiteral | ComparisonLiteral):
                raise ValueError("head modes require basic literals")
            if self.head_form is None or self.head is None:
                raise ValueError("head modes require a complete head form")
        elif self.head_form is not None or self.head is not None:
            raise ValueError("body modes cannot belong to a head form")
        object.__setattr__(
            self,
            "bindings",
            tuple(
                binding
                for index, term in enumerate(self.arguments)
                for binding in mode_terms.bindings(term, (index,))
            ),
        )

        object.__setattr__(self, "dependencies", self.literal.dependencies)

    def __hash__(self) -> int:
        # Equal modes share their id. Canonicalization caches key on modes, and
        # hashing the whole template tree dominated their lookups.
        return hash(self.id)

    @property
    def arity(self) -> int:
        return len(self.arguments)

    @property
    def guard_terms(self) -> tuple[ast.AST, ...]:
        return self.head.guard_terms if self.head is not None and self.head_position == 0 else ()

    @property
    def arguments(self) -> tuple[ast.AST, ...]:
        return (*self.literal.arguments, *self.guard_terms)

    @property
    def binding_positions(self) -> tuple[int, ...]:
        if isinstance(
            self.literal,
            AggregateLiteral | ConditionalLiteral | ComparisonLiteral | ArithmeticLiteral | HeadAggregateElement,
        ) or self.guard_terms or (
            isinstance(self.literal, AtomLiteral)
            and (
                self.literal.atom.alternatives
                or any(mode_terms.kind(term) in {"function", "tuple", "arithmetic", "interval", "pool"} for term in self.literal.atom.terms)
            )
        ):
            return tuple(range(len(self.bindings)))
        return tuple(binding.path[0] for binding in self.bindings)

    @property
    def condition_count(self) -> int:
        return (
            len(self.literal.conditions)
            if isinstance(self.literal, ConditionalLiteral | HeadAggregateElement)
            else 0
        )
