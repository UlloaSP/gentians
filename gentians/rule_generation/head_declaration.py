from dataclasses import dataclass

from .mode_declaration import ModeDeclaration


@dataclass(frozen=True, slots=True)
class HeadDeclaration:
    """One complete allowed rule head."""

    recall: int
    kind: str
    atoms: tuple[ModeDeclaration, ...]
    lower: int | None = None
    upper: int | None = None

    def __post_init__(self) -> None:
        if self.recall != 1:
            raise ValueError("complete head modes require recall 1")
        if self.kind not in {"normal", "disjunction", "choice"}:
            raise ValueError(f"invalid head mode kind: {self.kind}")
        if not self.atoms:
            raise ValueError("head modes require at least one atom")
        if self.kind == "normal" and len(self.atoms) != 1:
            raise ValueError("normal head modes require exactly one atom")
        if self.kind != "choice" and (self.lower is not None or self.upper is not None):
            raise ValueError("only choice heads accept cardinality bounds")
        if self.lower is not None and self.lower < 0:
            raise ValueError("head lower bound cannot be negative")
        if self.upper is not None and self.upper < 0:
            raise ValueError("head upper bound cannot be negative")
        if self.lower is not None and self.upper is not None and self.lower > self.upper:
            raise ValueError("head lower bound cannot exceed upper bound")
        if self.lower is not None and self.lower > len(self.atoms):
            raise ValueError("head lower bound exceeds element count")
        if self.upper is not None and self.upper > len(self.atoms):
            raise ValueError("head upper bound exceeds element count")

        labels: dict[str, str] = {}
        for atom in self.atoms:
            if not atom.head or not atom.positive:
                raise ValueError("head elements must be positive head atoms")
            for argument in atom.arguments:
                if not argument.label:
                    continue
                previous = labels.setdefault(argument.label, argument.type)
                if previous != argument.type:
                    raise ValueError(
                        f"head variable label {argument.label} has incompatible types"
                    )

    @property
    def width(self) -> int:
        return len(self.atoms)
