from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Coverage:
    pos_mask: int = 0
    neg_mask: int = 0
