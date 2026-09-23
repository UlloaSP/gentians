from collections.abc import Iterator
from dataclasses import dataclass
from itertools import product

from .atom_literal import AtomLiteral
from .boolean_literal import BooleanLiteral
from .comparison_literal import ComparisonLiteral
from .term_template import TermTemplate


@dataclass(frozen=True, slots=True)
class AggregateElement:
    terms: tuple[TermTemplate, ...]
    conditions: tuple[AtomLiteral | BooleanLiteral | ComparisonLiteral, ...]
    conclusion: AtomLiteral | BooleanLiteral | ComparisonLiteral | None = None

    def __post_init__(self) -> None:
        if self.conclusion is not None and self.terms:
            raise ValueError("aggregate element needs a tuple or a set atom")

    @property
    def arguments(self) -> tuple[TermTemplate, ...]:
        return (
            *self.terms,
            *(self.conclusion.arguments if self.conclusion is not None else ()),
            *(term for condition in self.conditions for term in condition.arguments),
        )

    def concretizations(
        self, constants: dict[str, tuple[str, ...]]
    ) -> tuple["AggregateElement", ...]:
        return tuple(
            AggregateElement(
                terms, conditions, conclusion,
            )
            for terms in product(*(term.concretizations(constants) for term in self.terms))
            for conclusion in (
                tuple(
                    AtomLiteral(atom, self.conclusion.default_negated, self.conclusion.double_negated)
                    for atom in self.conclusion.atom.concretizations(constants)
                ) if isinstance(self.conclusion, AtomLiteral) else
                tuple(
                    ComparisonLiteral(terms, self.conclusion.operators,
                                      self.conclusion.default_negated,
                                      double_negated=self.conclusion.double_negated)
                    for terms in product(
                        *(term.concretizations(constants) for term in self.conclusion.terms)
                    )
                ) if isinstance(self.conclusion, ComparisonLiteral) else
                (self.conclusion,)
            )
            for conditions in product(
                *(
                    tuple(
                        AtomLiteral(atom, condition.default_negated,
                                    condition.double_negated)
                        for atom in condition.atom.concretizations(constants)
                    ) if isinstance(condition, AtomLiteral) else (condition,) if isinstance(condition, BooleanLiteral) else tuple(
                        ComparisonLiteral(
                            terms, condition.operators, condition.default_negated,
                            double_negated=condition.double_negated,
                        )
                        for terms in product(
                            *(term.concretizations(constants) for term in condition.terms)
                        )
                    )
                    for condition in self.conditions
                )
            )
        )

    def render(self, variables: Iterator[str]) -> str:
        terms = ",".join(
            f"({rendered})" if term.kind == "pool" else rendered
            for term in self.terms
            for rendered in (term.render(variables),)
        )
        if self.conclusion is not None:
            terms += self.conclusion.render(variables)
        conditions = ",".join(condition.render(variables) for condition in self.conditions)
        return f"{terms}:{conditions}" if conditions else terms
