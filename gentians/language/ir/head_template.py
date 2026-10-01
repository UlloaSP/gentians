from dataclasses import dataclass, replace
from itertools import product
from typing import TypeAlias

from clingo import ast

from .. import terms as mode_terms
from ..ast_nodes import LOCATION, consume_all, literal
from .atom_literal import AtomLiteral
from .boolean_literal import BooleanLiteral
from .comparison_literal import ComparisonLiteral
from .conditional_literal import ConditionalLiteral
from .head_aggregate_element import HeadAggregateElement
from .literal_template import anonymous_is_safe

HeadElement: TypeAlias = (
    AtomLiteral
    | BooleanLiteral
    | ComparisonLiteral
    | ConditionalLiteral
    | HeadAggregateElement
)
_NORMAL_FORM = literal(ast.BooleanConstant(True))


def _integer_bound(term: ast.AST) -> int | None:
    try:
        return int(str(term))
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class HeadTemplate:
    # Clingo owns the form, guards and aggregate function. Element syntax is
    # filled at instantiation; each learning element keeps its own conditions.
    form: ast.AST
    elements: tuple[HeadElement, ...]

    def __post_init__(self) -> None:
        kind = self.kind
        guard_terms = self.guard_terms
        if kind == "normal" and len(self.elements) != 1:
            raise ValueError("normal head modes require exactly one literal")
        if kind == "disjunction" and not self.elements:
            raise ValueError("disjunctive heads require an element")
        if any(mode_terms.contains_anonymous(term) for term in guard_terms):
            raise ValueError("anonymous variables cannot occur in a head")
        if any(
            not anonymous_is_safe(element, positive_atom=False)
            for element in self.elements
        ):
            raise ValueError("anonymous variables need a positive head condition atom")
        if any(
            isinstance(item, HeadAggregateElement) != (kind == "aggregate")
            for item in self.elements
        ):
            raise ValueError("head elements must match their Clingo form")
        mode_terms.validate_labels(
            (
                *(term for element in self.elements for term in element.arguments),
                *guard_terms,
            ),
            "head",
        )
        if any(
            binding.direction not in {"input", "any"}
            for term in guard_terms
            for binding in mode_terms.bindings(term)
        ):
            raise ValueError("head guards require input or any variables")
        if kind == "choice":
            left, right = self.form.left_guard, self.form.right_guard
            if (
                left
                and right
                and left.comparison
                == right.comparison
                == ast.ComparisonOperator.LessEqual
            ):
                lower, upper = _integer_bound(left.term), _integer_bound(right.term)
                if lower is not None and upper is not None and lower > upper:
                    raise ValueError("head lower bound cannot exceed upper bound")

    @classmethod
    def normal(
        cls,
        element: AtomLiteral | BooleanLiteral | ComparisonLiteral | ConditionalLiteral,
    ) -> "HeadTemplate":
        return cls(_NORMAL_FORM, (element,))

    @property
    def kind(self) -> str:
        match self.form.ast_type:
            case ast.ASTType.Literal | ast.ASTType.ConditionalLiteral:
                return "normal"
            case ast.ASTType.Disjunction:
                return "disjunction"
            case ast.ASTType.Aggregate:
                return "choice"
            case ast.ASTType.HeadAggregate:
                return "aggregate"
        raise ValueError(f"unsupported Clingo head form: {self.form.ast_type}")

    @property
    def guard_terms(self) -> tuple[ast.AST, ...]:
        kind = self.kind
        if kind not in {"choice", "aggregate"}:
            return ()
        return tuple(
            guard.term
            for guard in (self.form.left_guard, self.form.right_guard)
            if guard is not None
            and (kind == "aggregate" or _integer_bound(guard.term) is None)
        )

    @property
    def arguments(self) -> tuple[ast.AST, ...]:
        return (
            *(term for element in self.elements for term in element.arguments),
            *self.guard_terms,
        )

    @property
    def conclusions(
        self,
    ) -> tuple[AtomLiteral | BooleanLiteral | ComparisonLiteral, ...]:
        return tuple(
            element.conclusion
            if isinstance(element, ConditionalLiteral | HeadAggregateElement)
            else element
            for element in self.elements
        )

    @property
    def conditions(
        self,
    ) -> tuple[AtomLiteral | BooleanLiteral | ComparisonLiteral, ...]:
        return tuple(
            condition
            for element in self.elements
            if isinstance(element, ConditionalLiteral | HeadAggregateElement)
            for condition in element.conditions
        )

    @property
    def width(self) -> int:
        return len(self.elements)

    def concretizations(
        self, constants: dict[str, tuple[ast.AST, ...]]
    ) -> tuple["HeadTemplate", ...]:
        forms = (self.form,)
        if self.kind in {"choice", "aggregate"}:

            def guards(guard: ast.AST | None) -> tuple[ast.AST | None, ...]:
                return (
                    tuple(
                        guard if term == guard.term else guard.update(term=term)
                        for term in mode_terms.concretizations(guard.term, constants)
                    )
                    if guard
                    else (None,)
                )

            forms = tuple(
                self.form if left == self.form.left_guard and right == self.form.right_guard
                else self.form.update(left_guard=left, right_guard=right)
                for left, right in product(
                    guards(self.form.left_guard), guards(self.form.right_guard)
                )
            )
        return tuple(
            self if form == self.form and elements == self.elements
            else replace(self, form=form, elements=elements)
            for form, elements in product(
                forms,
                product(*(element.concretizations(constants) for element in self.elements)),
            )
        )

    def instantiate(
        self, elements: tuple[ast.AST, ...], guard_variables: tuple[str, ...] = ()
    ) -> ast.AST:
        variables = iter(guard_variables)
        kind = self.kind
        if kind == "normal":
            if len(elements) != 1:
                raise ValueError("normal #modeh form must contain one literal")
            head = elements[0]
            if head.ast_type == ast.ASTType.ConditionalLiteral:
                head = ast.Disjunction(LOCATION, [head])
        else:
            items = list(elements) if self.elements else []
            if kind != "aggregate":
                items = [
                    item
                    if item.ast_type == ast.ASTType.ConditionalLiteral
                    else ast.ConditionalLiteral(LOCATION, item, [])
                    for item in items
                ]
            guards: dict[str, ast.AST | None] = {}
            if kind in {"choice", "aggregate"}:
                guards = {
                    side: guard.update(
                        term=mode_terms.instantiate(guard.term, variables)
                    )
                    if guard
                    else None
                    for side in ("left_guard", "right_guard")
                    for guard in (getattr(self.form, side),)
                }
            head = self.form.update(elements=items, **guards)
        consume_all(variables)
        return head
