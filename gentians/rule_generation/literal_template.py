from typing import TypeAlias

from .aggregate_literal import AggregateLiteral
from .arithmetic_literal import ArithmeticLiteral
from .atom_literal import AtomLiteral
from .comparison_literal import ComparisonLiteral
from .conditional_literal import ConditionalLiteral

LiteralTemplate: TypeAlias = (
    AtomLiteral
    | ComparisonLiteral
    | ArithmeticLiteral
    | AggregateLiteral
    | ConditionalLiteral
)


def render_literal(template: LiteralTemplate, variables: tuple[int, ...]) -> str:
    rendered_variables = iter(f"V{variable}" for variable in variables)
    rendered = template.render(rendered_variables)
    try:
        next(rendered_variables)
    except StopIteration:
        return rendered
    raise ValueError("literal has more variables than syntax bindings")
