from dataclasses import dataclass

from .atom_literal import AtomLiteral
from .atom_template import AtomTemplate
from .comparison_literal import ComparisonLiteral
from .aggregate_guard import AggregateGuard
from .head_aggregate_element import HeadAggregateElement


@dataclass(frozen=True, slots=True)
class HeadTemplate:
    kind: str
    elements: tuple[AtomTemplate, ...]
    lower: int | None = None
    upper: int | None = None
    conditions: tuple[tuple[AtomLiteral | ComparisonLiteral, ...], ...] = ()
    aggregate_elements: tuple[HeadAggregateElement, ...] = ()
    aggregate_function: str = ""
    aggregate_left_guard: AggregateGuard | None = None
    aggregate_right_guard: AggregateGuard | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"normal", "disjunction", "choice", "aggregate"}:
            raise ValueError(f"invalid head mode kind: {self.kind}")
        if not self.elements:
            raise ValueError("head modes require at least one atom")
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
        if self.lower is not None and self.lower < 0:
            raise ValueError("head lower bound cannot be negative")
        if self.upper is not None and self.upper < 0:
            raise ValueError("head upper bound cannot be negative")
        if (
            self.lower is not None
            and self.upper is not None
            and self.lower > self.upper
        ):
            raise ValueError("head lower bound cannot exceed upper bound")
        if self.lower is not None and self.lower > len(self.elements):
            raise ValueError("head lower bound exceeds element count")
        if self.upper is not None and self.upper > len(self.elements):
            raise ValueError("head upper bound exceeds element count")

        labels: dict[str, str] = {}
        for atom, conditions in zip(self.elements, self.conditions, strict=True):
            bindings = (
                *atom.bindings(),
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

    @property
    def width(self) -> int:
        return len(self.elements)

    def render(self, atoms: tuple[str, ...]) -> str:
        if self.kind == "normal":
            if len(atoms) != 1:
                raise ValueError("normal #modeh form must contain one atom")
            return atoms[0]
        if self.kind == "disjunction":
            return ";".join(atoms)
        if self.kind == "aggregate":
            core = f"#{self.aggregate_function}" + "{" + ";".join(atoms) + "}"
            if self.aggregate_left_guard is not None:
                guard = self.aggregate_left_guard
                value = guard.term.render(iter(()))
                core = f"{core}={value}" if guard.operator == "=" else f"{value}{guard.operator}{core}"
            if self.aggregate_right_guard is not None:
                guard = self.aggregate_right_guard
                core = f"{core}{guard.operator}{guard.term.render(iter(()))}"
            return core
        lower = "" if self.lower is None else self.lower
        upper = "" if self.upper is None else self.upper
        return f"{lower}{{{';'.join(atoms)}}}{upper}"
