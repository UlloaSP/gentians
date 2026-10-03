from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ReifiedLiteral:
    section: str
    slot: int
    mode_id: int
    variables: tuple[int, ...]
    key: tuple[int, tuple[int, ...]] = field(init=False, repr=False, compare=False)
    variable_mask: int = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", (self.mode_id, self.variables))
        mask = 0
        for variable in self.variables:
            mask |= 1 << variable
        object.__setattr__(self, "variable_mask", mask)
