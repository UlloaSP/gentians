from typing import TypeAlias

from clingo import ast

from .. import terms as mode_terms
from .aggregate_literal import AggregateLiteral
from .atom_literal import AtomLiteral
from .boolean_literal import BooleanLiteral
from .comparison_literal import ComparisonLiteral
from .conditional_literal import ConditionalLiteral
from .head_aggregate_element import HeadAggregateElement

LiteralTemplate: TypeAlias = (
    AtomLiteral
    | BooleanLiteral
    | ComparisonLiteral
    | AggregateLiteral
    | ConditionalLiteral
    | HeadAggregateElement
)


def anonymous_is_safe(template: LiteralTemplate, *, positive_atom: bool = True) -> bool:
    """Anonymous terms are allowed only in positive grounding atoms.

    Conclusions and aggregate tuples never provide that grounding position;
    conditions retain their own atom polarity and scope.
    """

    def without_anonymous(terms: tuple[ast.AST, ...]) -> bool:
        return not any(mode_terms.contains_anonymous(term) for term in terms)

    if isinstance(template, ConditionalLiteral | HeadAggregateElement):
        return (
            anonymous_is_safe(template.conclusion, positive_atom=False)
            and (
                not isinstance(template, HeadAggregateElement)
                or without_anonymous(template.terms)
            )
            and all(anonymous_is_safe(condition) for condition in template.conditions)
        )
    if isinstance(template, AggregateLiteral):
        return all(
            without_anonymous(element.terms)
            and (
                element.conclusion is None
                or anonymous_is_safe(element.conclusion, positive_atom=False)
            )
            and all(anonymous_is_safe(condition) for condition in element.conditions)
            for element in template.elements
        ) and all(
            guard is None or without_anonymous((guard.term,))
            for guard in (template.left_guard, template.right_guard)
        )
    return (
        positive_atom
        and isinstance(template, AtomLiteral)
        and not template.default_negated
        or without_anonymous(template.arguments)
    )
