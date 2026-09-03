from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TermBinding:
    path: tuple[int, ...]
    type: str
    direction: str
    label: str
