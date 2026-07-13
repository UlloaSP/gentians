from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OperatorDeclaration:
    recall: int
    operator: str
