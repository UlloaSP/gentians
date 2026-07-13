from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReifiedLiteral:
    section: str
    slot: int
    mode_id: int
    variables: tuple[int, ...]
