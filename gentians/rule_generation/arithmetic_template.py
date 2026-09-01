from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ArithmeticTemplate:
    operator: str
    coefficients: tuple[int, ...] = ()
    complexity: int = 1

    @property
    def linear(self) -> bool:
        return bool(self.coefficients)
