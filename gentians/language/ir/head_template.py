from dataclasses import dataclass

from .atom_literal import AtomLiteral
from .boolean_literal import BooleanLiteral
from .atom_template import AtomTemplate
from .comparison_literal import ComparisonLiteral
from .aggregate_guard import AggregateGuard
from .head_aggregate_element import HeadAggregateElement
from .term_template import TermTemplate


@dataclass(frozen=True, slots=True)
class HeadTemplate:
    kind: str
    elements: tuple[AtomTemplate | BooleanLiteral | ComparisonLiteral, ...]
    lower: int | TermTemplate | None = None
    upper: int | TermTemplate | None = None
    conditions: tuple[tuple[AtomLiteral | BooleanLiteral | ComparisonLiteral, ...], ...] = ()
    aggregate_elements: tuple[HeadAggregateElement, ...] = ()
    aggregate_function: str = ""
    aggregate_left_guard: AggregateGuard | None = None
    aggregate_right_guard: AggregateGuard | None = None
    signs: tuple[int, ...] = ()
    lower_operator: str = "<="
    upper_operator: str = "<="

    def __post_init__(self) -> None:
        if self.kind not in {"normal", "disjunction", "choice", "aggregate"}:
            raise ValueError(f"invalid head mode kind: {self.kind}")
        if not self.elements and self.kind not in {"choice", "aggregate"}:
            raise ValueError("normal and disjunctive heads require an element")
        if not self.signs:
            object.__setattr__(self, "signs", (0,) * len(self.elements))
        elif len(self.signs) != len(self.elements) or any(sign not in {0, 1, 2} for sign in self.signs):
            raise ValueError("every head element requires one valid sign")
        if self.kind not in {"normal", "disjunction", "choice"} and any(self.signs):
            raise ValueError("this head form does not accept default negation")
        if not self.conditions:
            object.__setattr__(self, "conditions", tuple(() for _ in self.elements))
        elif len(self.conditions) != len(self.elements):
            raise ValueError("every head element requires one condition list")
        if self.kind == "normal" and len(self.elements) != 1:
            raise ValueError("normal head modes require exactly one atom")
        if self.kind == "aggregate" and (
            not self.aggregate_function
            or len(self.aggregate_elements) != len(self.elements)
            or tuple(item.atom for item in self.aggregate_elements) != self.elements
        ):
            raise ValueError("aggregate head elements must match their atoms")
        if self.kind != "choice" and (self.lower is not None or self.upper is not None):
            raise ValueError("only choice heads accept cardinality bounds")
        if (
            self.lower_operator == self.upper_operator == "<="
            and
            isinstance(self.lower, int)
            and isinstance(self.upper, int)
            and self.lower > self.upper
        ):
            raise ValueError("head lower bound cannot exceed upper bound")

        labels: dict[str, str] = {}
        for atom, conditions in zip(self.elements, self.conditions, strict=True):
            bindings = (
                *(atom.bindings() if isinstance(atom, AtomTemplate) else (
                    binding for term in atom.arguments for binding in term.bindings()
                )),
                *(
                    binding
                    for condition in conditions
                    for term in condition.arguments
                    for binding in term.bindings()
                ),
            )
            for binding in bindings:
                if not binding.label:
                    continue
                previous = labels.setdefault(binding.label, binding.type)
                if previous != binding.type:
                    raise ValueError(
                        f"head variable label {binding.label} has incompatible types"
                    )
        for element in self.aggregate_elements:
            for term in element.arguments:
                for binding in term.bindings():
                    if binding.label:
                        previous = labels.setdefault(binding.label, binding.type)
                        if previous != binding.type:
                            raise ValueError(
                                f"head variable label {binding.label} has incompatible types"
                            )

        for term in self.guard_terms:
            for binding in term.bindings():
                if binding.direction not in {"input", "any"}:
                    raise ValueError("head guards require input or any variables")
                if binding.label:
                    previous = labels.setdefault(binding.label, binding.type)
                    if previous != binding.type:
                        raise ValueError(
                            f"head variable label {binding.label} has incompatible types"
                        )

    @property
    def guard_terms(self) -> tuple[TermTemplate, ...]:
        if self.kind == "choice":
            return tuple(
                value for value in (self.lower, self.upper)
                if isinstance(value, TermTemplate)
            )
        if self.kind == "aggregate":
            return tuple(
                guard.term for guard in (
                    self.aggregate_left_guard, self.aggregate_right_guard
                ) if guard is not None
            )
        return ()

    @property
    def width(self) -> int:
        return len(self.elements)

    def render(self, atoms: tuple[str, ...], guard_variables: tuple[str, ...] = ()) -> str:
        variables = iter(guard_variables)
        if self.kind == "normal":
            if len(atoms) != 1:
                raise ValueError("normal #modeh form must contain one atom")
            return atoms[0]
        if self.kind == "disjunction":
            return ";".join(atoms)
        if self.kind == "aggregate":
            core = f"#{self.aggregate_function}" + "{" + ";".join(atoms if self.elements else ()) + "}"
            if self.aggregate_left_guard is not None:
                guard = self.aggregate_left_guard
                value = guard.term.render(variables)
                if guard.term.kind == "pool":
                    value = f"({value})"
                core = f"{core}={value}" if guard.operator == "=" else f"{value}{guard.operator}{core}"
            if self.aggregate_right_guard is not None:
                guard = self.aggregate_right_guard
                value = guard.term.render(variables)
                if guard.term.kind == "pool":
                    value = f"({value})"
                core = f"{core}{guard.operator}{value}"
            return core
        lower = "" if self.lower is None else (
            self.lower.render(variables) if isinstance(self.lower, TermTemplate) else self.lower
        )
        upper = "" if self.upper is None else (
            self.upper.render(variables) if isinstance(self.upper, TermTemplate) else self.upper
        )
        if isinstance(self.lower, TermTemplate) and self.lower.kind == "pool":
            lower = f"({lower})"
        if isinstance(self.upper, TermTemplate) and self.upper.kind == "pool":
            upper = f"({upper})"
        left = f"{lower}{self.lower_operator}" if self.lower is not None and self.lower_operator != "<=" else str(lower)
        right = f"{self.upper_operator}{upper}" if self.upper is not None and self.upper_operator != "<=" else str(upper)
        return f"{left}{{{';'.join(atoms if self.elements else ())}}}{right}"
