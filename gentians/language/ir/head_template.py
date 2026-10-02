from dataclasses import dataclass, field, replace
from collections.abc import Iterable, Iterator
from typing import TypeAlias

import clingo
from clingo import ast

from .. import terms as mode_terms
from ..asp import AspProgram, add_program
from ..ast_nodes import LOCATION, binding_terms, consume_all, literal
from ..grammar import SourceError
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


def _integer_bounds(terms: Iterable[ast.AST], definitions: AspProgram) -> Iterator[int]:
    for term in terms:
        value = _integer_bound(term)
        if value is not None:
            yield value
            continue
        if mode_terms.bindings(term):
            continue
        # One live variant and control: no Cartesian pool in Python or Clingo.
        # Clingo evaluates arithmetic and resolves #const; Python does neither.
        control = clingo.Control(logger=lambda _code, _message: None)
        fact = ast.Rule(LOCATION, literal(ast.SymbolicAtom(
            ast.Function(LOCATION, "__gentians_bound", [term], False),
        )), [])
        add_program(control, (*definitions, fact))
        control.ground([("base", [])])
        for atom in control.symbolic_atoms.by_signature("__gentians_bound", 1):
            value = atom.symbol.arguments[0]
            if value.type == clingo.SymbolType.Number:
                yield value.number


@dataclass(frozen=True, slots=True)
class HeadTemplate:
    # Clingo owns the form, guards and aggregate function. Element syntax is
    # filled at instantiation; each learning element keeps its own conditions.
    form: ast.AST
    elements: tuple[HeadElement, ...]
    arguments: tuple[ast.AST, ...] = field(init=False, repr=False, compare=False)
    guard_terms: tuple[ast.AST, ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        kind = self.kind
        guard_terms = tuple(
            guard.term for guard in (self.form.left_guard, self.form.right_guard)
            if guard is not None and (kind == "aggregate" or _integer_bound(guard.term) is None)
        ) if kind in {"choice", "aggregate"} else ()
        object.__setattr__(self, "guard_terms", guard_terms)
        object.__setattr__(self, "arguments", (
            *(term for element in self.elements for term in element.arguments),
            *guard_terms,
        ))
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
                    raise SourceError.at_node(left.term, "head lower bound cannot exceed upper bound")

    def validate_constants(self, constants: dict[str, tuple[ast.AST, ...]], definitions: AspProgram = ()) -> None:
        if self.kind != "choice":
            return
        left, right = self.form.left_guard, self.form.right_guard
        if left is None or right is None or left.comparison != right.comparison or left.comparison != ast.ComparisonOperator.LessEqual:
            return
        def values(term: ast.AST) -> Iterator[int]:
            try:
                yield from _integer_bounds(mode_terms.concretizations(term, constants), definitions)
            except RuntimeError as error:
                raise SourceError.at_node(term, f"invalid head bound: {error}") from None

        lower = max(values(left.term), default=None)
        upper = min(values(right.term), default=None)
        if lower is not None and upper is not None and lower > upper:
            raise SourceError.at_node(left.term, "head lower bound cannot exceed upper bound")

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
    ) -> Iterator["HeadTemplate"]:
        self.validate_constants(constants)
        if not any(mode_terms.constant_types(term) for term in self.arguments):
            yield self
            return
        guarded = self.kind in {"choice", "aggregate"}
        # Head guards are the outer alternatives; preserve their declared order.
        guards = (self.form.left_guard, self.form.right_guard) if guarded else ()
        terms = (
            *(guard.term for guard in guards if guard is not None),
            *(term for element in self.elements for term in element.arguments),
        )
        for concrete in mode_terms.concretize_terms(terms, constants):
            arguments = iter(concrete)
            form = self.form
            if guarded:
                left = mode_terms.replace_guard_term(self.form.left_guard, arguments)
                right = mode_terms.replace_guard_term(self.form.right_guard, arguments)
                if left != self.form.left_guard or right != self.form.right_guard:
                    form = self.form.update(left_guard=left, right_guard=right)
            elements = tuple(element.with_arguments(arguments) for element in self.elements)
            yield (
                self if form == self.form and elements == self.elements
                else replace(self, form=form, elements=elements)
            )

    def instantiate(
        self, elements: tuple[ast.AST, ...], guard_variables: tuple[str, ...] = ()
    ) -> ast.AST:
        variables = binding_terms(guard_variables)
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
                for side in ("left_guard", "right_guard"):
                    guards[side] = mode_terms.instantiate_guard(getattr(self.form, side), variables)
            head = self.form.update(elements=items, **guards)
        consume_all(variables)
        return head
