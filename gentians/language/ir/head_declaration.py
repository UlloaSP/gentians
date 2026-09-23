from dataclasses import dataclass

from .atom_literal import AtomLiteral
from .atom_template import AtomTemplate
from .head_template import HeadTemplate


@dataclass(frozen=True, slots=True)
class HeadDeclaration:
    recall: int
    template: HeadTemplate

    def __post_init__(self) -> None:
        if self.recall != 1:
            raise ValueError("complete head modes require recall 1")
        terms = (
            term
            for element in self.template.elements
            for term in (
                element.binding_terms if isinstance(element, AtomTemplate)
                else element.arguments
            )
        )
        terms = (
            *terms,
            *self.template.guard_terms,
            *(term for element in self.template.aggregate_elements for term in element.terms),
        )
        if any(term.contains_anonymous for term in terms):
            raise ValueError("anonymous variables cannot occur in a head")
        if any(
            term.contains_anonymous
            for element in self.template.aggregate_elements
            for term in (
                element.atom.binding_terms if isinstance(element.atom, AtomTemplate)
                else element.atom.arguments
            )
        ):
            raise ValueError("anonymous variables cannot occur in a head")
        conditions = (
            *(condition for group in self.template.conditions for condition in group),
            *(condition for element in self.template.aggregate_elements
              for condition in element.conditions),
        )
        if any(
            any(term.contains_anonymous for term in condition.arguments)
            and (not isinstance(condition, AtomLiteral) or condition.default_negated)
            for condition in conditions
        ):
            raise ValueError("anonymous variables need a positive head condition atom")
    @property
    def width(self) -> int:
        return self.template.width
