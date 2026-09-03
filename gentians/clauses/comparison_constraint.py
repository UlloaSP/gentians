from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ComparisonConstraint:
    left: int
    right: int
    operator: str

    @property
    def variables(self) -> frozenset[int]:
        return frozenset((self.left, self.right))

    @property
    def key(self) -> tuple[object, ...]:
        variables = (self.left, self.right)
        if self.operator in {"=", "!="}:
            variables = tuple(sorted(variables))
        return "comparison", self.operator, variables

    def render(self) -> str:
        return f"V{self.left}{self.operator}V{self.right}"

    def remap(self, variables: dict[int, int]) -> "ComparisonConstraint":
        return ComparisonConstraint(
            variables[self.left], variables[self.right], self.operator
        )
