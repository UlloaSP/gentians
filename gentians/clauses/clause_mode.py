from dataclasses import dataclass, field
from itertools import accumulate

from clingo import ast

from ..language import terms as mode_terms
from ..language.asp import Predicate
from ..language.ir.aggregate_literal import AggregateLiteral
from .arithmetic_literal import ArithmeticLiteral
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
    literal: LiteralTemplate | ArithmeticLiteral
    head_form: int | None = None
    head_position: int = 0
    head: HeadTemplate | None = None
    arguments: tuple[ast.AST, ...] = field(init=False, repr=False, compare=False)
    guard_terms: tuple[ast.AST, ...] = field(init=False, repr=False, compare=False)
    binding_positions: tuple[int, ...] = field(init=False, repr=False, compare=False)
    argument_offsets: tuple[int, ...] = field(init=False, repr=False, compare=False)
    output_guard: ast.AST | None = field(init=False, repr=False, compare=False)
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
    builtin: bool = field(init=False, repr=False, compare=False)
    positive_atom: bool = field(init=False, repr=False, compare=False)
    numeric_builtin: bool = field(init=False, repr=False, compare=False)
    numeric_positions: tuple[int, ...] = field(init=False, repr=False, compare=False)
    head_predicates: frozenset[Predicate] = field(init=False, repr=False, compare=False)
    head_dependencies: frozenset[Predicate] = field(init=False, repr=False, compare=False)
    condition_count: int = field(init=False, repr=False, compare=False)
    arithmetic_steps: tuple[tuple[str, int], ...] = field(init=False, repr=False, compare=False)
    comparison_steps: tuple[tuple[tuple[str, str | int, int], ...], ...] = field(init=False, repr=False, compare=False)
    _hash: int | None = field(default=None, init=False, repr=False, compare=False)

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
        guards = self.head.guard_terms if self.head is not None and self.head_position == 0 else ()
        object.__setattr__(self, "guard_terms", guards)
        object.__setattr__(self, "arguments", (*self.literal.arguments, *guards))
        object.__setattr__(self, "output_guard", self.literal.output_guard if isinstance(self.literal, AggregateLiteral) else None)
        object.__setattr__(
            self,
            "bindings",
            tuple(
                binding
                for index, term in enumerate(self.arguments)
                for binding in mode_terms.bindings(term, (index,))
            ),
        )

        counts = [0] * len(self.arguments)
        for binding in self.bindings:
            counts[binding.path[0]] += 1
        object.__setattr__(self, "argument_offsets", tuple(accumulate(counts, initial=0)))

        object.__setattr__(self, "dependencies", self.literal.dependencies)
        head_predicates: set[Predicate] = set()
        head_dependencies: set[Predicate] = set()
        if self.section == "head":
            if isinstance(conclusion, AtomLiteral):
                (head_dependencies if conclusion.default_negated else head_predicates).add(conclusion.atom.signature)
            if isinstance(self.literal, ConditionalLiteral):
                head_dependencies.update(
                    predicate for condition in self.literal.conditions for predicate in condition.dependencies
                )
            elif isinstance(self.literal, HeadAggregateElement):
                head_dependencies.update(self.literal.dependencies)
        object.__setattr__(self, "head_predicates", frozenset(head_predicates))
        object.__setattr__(self, "head_dependencies", frozenset(head_dependencies))
        object.__setattr__(self, "condition_count", len(self.literal.conditions)
                           if isinstance(self.literal, ConditionalLiteral | HeadAggregateElement) else 0)
        steps: list[tuple[str, int]] = []
        if isinstance(self.literal, ArithmeticLiteral):
            absolute = self.literal.operator == "abs"
            roots = self.literal.arguments[:-1] if absolute else (self.literal.expression,)
            for root in roots:
                for node, count in mode_terms._postorder(root):
                    kind = mode_terms.kind(node)
                    operator = "" if kind == "variable" else mode_terms.value(node) if kind == "arithmetic" else "unsupported"
                    steps.append((operator, count))
            if absolute:
                steps.append(("abs", len(roots)))
        object.__setattr__(self, "arithmetic_steps", tuple(steps))
        object.__setattr__(self, "comparison_steps", tuple(
            _comparison_steps(term) for term in self.literal.terms
        ) if isinstance(self.literal, ComparisonLiteral) else ())
        comparison = isinstance(self.literal, ComparisonLiteral)
        arithmetic = isinstance(self.literal, ArithmeticLiteral)
        numeric = all(binding.type == "numeric" for binding in self.bindings)
        object.__setattr__(self, "builtin", arithmetic or (
            comparison and not self.literal.default_negated and bool(self.bindings)
            and (self.literal.canonicalizable or self.literal.arithmetic or numeric)
        ))
        object.__setattr__(self, "positive_atom", isinstance(self.literal, AtomLiteral) and not self.literal.default_negated)
        object.__setattr__(self, "numeric_builtin", arithmetic or comparison and (self.literal.arithmetic or numeric))
        object.__setattr__(self, "numeric_positions", tuple(index for index, binding in enumerate(self.bindings) if binding.type == "numeric"))
        positions = (
            tuple(range(len(self.bindings)))
            if isinstance(
                self.literal,
                AggregateLiteral | ConditionalLiteral | ComparisonLiteral | ArithmeticLiteral | HeadAggregateElement,
            ) or guards or (
                isinstance(self.literal, AtomLiteral)
                and (
                    self.literal.atom.alternatives
                    or any(mode_terms.kind(term) in {"function", "tuple", "arithmetic", "interval", "pool"} for term in self.literal.atom.terms)
                )
            )
            else tuple(binding.path[0] for binding in self.bindings)
        )
        object.__setattr__(self, "binding_positions", positions)

    def __hash__(self) -> int:
        cached = self._hash
        if cached is None:
            cached = hash((self.id, self.recall_group, self.section, self.recall,
                           self.literal, self.head_form, self.head_position, self.head))
            object.__setattr__(self, "_hash", cached)
        return cached

    @property
    def arity(self) -> int:
        return len(self.arguments)

    @property
    def literal_binding_count(self) -> int:
        return self.argument_offsets[len(self.arguments) - len(self.guard_terms)]


def _comparison_steps(term: ast.AST) -> tuple[tuple[str, str | int, int], ...]:
    steps: list[tuple[str, str | int, int]] = []
    for node, count in mode_terms._postorder(term):
        kind = mode_terms.kind(node)
        value: str | int = ""
        if kind == "fixed":
            value = mode_terms.value(node)
            try:
                value = int(value)
                kind = "number"
            except ValueError:
                pass
        elif kind not in {"variable", "constant"}:
            value = mode_terms.value(node)
            value = {"function": f"function:{value}", "tuple": "tuple", "interval": "interval"}.get(kind, value)
            kind = "expression"
        steps.append((kind, value, count))
    return tuple(steps)
