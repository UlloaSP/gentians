from collections.abc import Iterator
from dataclasses import dataclass
from itertools import product

from ..asp import Predicate
from .atom_template import AtomTemplate
from .atom_literal import AtomLiteral
from .boolean_literal import BooleanLiteral
from .comparison_literal import ComparisonLiteral
from .term_template import TermTemplate


@dataclass(frozen=True, slots=True)
class HeadAggregateElement:
    terms: tuple[TermTemplate, ...]
    atom: AtomTemplate | BooleanLiteral | ComparisonLiteral
    conditions: tuple[AtomLiteral | BooleanLiteral | ComparisonLiteral, ...]
    default_negated: bool = False
    double_negated: bool = False

    def __post_init__(self) -> None:
        if self.double_negated and not self.default_negated:
            raise ValueError("double negation requires default negation")

    @property
    def kind(self) -> str:
        return "head_aggregate"

    @property
    def arguments(self) -> tuple[TermTemplate, ...]:
        return (
            *self.terms,
            *(self.atom.binding_terms if isinstance(self.atom, AtomTemplate) else self.atom.arguments),
            *(term for condition in self.conditions for term in condition.arguments),
        )

    @property
    def dependencies(self) -> frozenset[Predicate]:
        dependencies = {
            dependency
            for literal in self.conditions
            for dependency in literal.dependencies
        }
        if isinstance(self.atom, AtomTemplate):
            if self.default_negated:
                dependencies.add(self.atom.signature)
        else:
            dependencies.update(self.atom.dependencies)
        return frozenset(dependencies)

    def concretizations(
        self, constants: dict[str, tuple[str, ...]]
    ) -> tuple["HeadAggregateElement", ...]:
        if isinstance(self.atom, AtomTemplate):
            conclusions: tuple[AtomTemplate | BooleanLiteral | ComparisonLiteral, ...] = (
                self.atom.concretizations(constants)
            )
        elif isinstance(self.atom, BooleanLiteral):
            conclusions = (self.atom,)
        else:
            conclusions = tuple(
                ComparisonLiteral(
                    terms, self.atom.operators, self.atom.default_negated,
                    double_negated=self.atom.double_negated,
                )
                for terms in product(
                    *(term.concretizations(constants) for term in self.atom.terms)
                )
            )
        return tuple(
            HeadAggregateElement(
                terms, atom, conditions, self.default_negated, self.double_negated
            )
            for terms in product(*(term.concretizations(constants) for term in self.terms))
            for atom in conclusions
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
        atom = (
            AtomLiteral(self.atom, self.default_negated, self.double_negated)
            if isinstance(self.atom, AtomTemplate) else self.atom
        ).render(variables)
        conditions = ",".join(condition.render(variables) for condition in self.conditions)
        return f"{terms}:{atom}:{conditions}" if conditions else f"{terms}:{atom}"
