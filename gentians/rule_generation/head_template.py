from dataclasses import dataclass

from .atom_literal import AtomLiteral
from .atom_template import AtomTemplate
from .comparison_literal import ComparisonLiteral


@dataclass(frozen=True, slots=True)
class HeadTemplate:
    kind: str
    elements: tuple[AtomTemplate, ...]
    lower: int | None = None
    upper: int | None = None
    conditions: tuple[tuple[AtomLiteral | ComparisonLiteral, ...], ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in {"normal", "disjunction", "choice"}:
            raise ValueError(f"invalid head mode kind: {self.kind}")
        if not self.elements:
            raise ValueError("head modes require at least one atom")
        if not self.conditions:
            object.__setattr__(self, "conditions", tuple(() for _ in self.elements))
        elif len(self.conditions) != len(self.elements):
            raise ValueError("every head element requires one condition list")
        if self.kind == "normal" and len(self.elements) != 1:
            raise ValueError("normal head modes require exactly one atom")
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
        lower = "" if self.lower is None else self.lower
        upper = "" if self.upper is None else self.upper
        return f"{lower}{{{';'.join(atoms)}}}{upper}"
