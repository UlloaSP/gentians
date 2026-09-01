from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True, slots=True)
class LinearConstraint:
    coefficients: tuple[Fraction, ...]
    relation: str

    @property
    def variables(self) -> frozenset[int]:
        return frozenset(
            index for index, coefficient in enumerate(self.coefficients) if coefficient
        )

    @property
    def key(self) -> tuple[object, ...]:
        return self.relation, self.coefficients

    def render(self) -> str:
        terms: list[tuple[str, int]] = []
        for variable, coefficient in enumerate(self.coefficients):
            if not coefficient:
                continue
            magnitude = abs(coefficient)
            value = (
                f"V{variable}"
                if magnitude == 1
                else f"{int(magnitude)}*V{variable}"
            )
            terms.append((value, 1 if coefficient > 0 else -1))
        expression = ""
        for value, sign in terms:
            if not expression:
                expression = value if sign > 0 else f"-{value}"
            else:
                expression += ("+" if sign > 0 else "-") + value
        operator = {"eq": "=", "lt": "<", "le": "<=", "ne": "!="}[
            self.relation
        ]
        return f"{expression}{operator}0"

    def remap(
        self, variables: dict[int, int], width: int
    ) -> "LinearConstraint":
        coefficients = [Fraction(0) for _ in range(width)]
        for variable, coefficient in enumerate(self.coefficients):
            if coefficient and variable in variables:
                coefficients[variables[variable]] += coefficient
        return LinearConstraint(tuple(coefficients), self.relation)
