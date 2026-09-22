from dataclasses import dataclass

from .expression import ArithmeticExpression


@dataclass(frozen=True, slots=True)
class TermComparisonConstraint:
    terms: tuple[ArithmeticExpression, ...]
    operators: tuple[str, ...]

    @property
    def variables(self) -> frozenset[int]:
        return frozenset().union(*(term.variables for term in self.terms))

    @property
    def key(self) -> tuple[object, ...]:
        keys = tuple(term.key for term in self.terms)
        if len(self.operators) == 1 and self.operators[0] in {"=", "!="}:
            keys = min(keys, tuple(reversed(keys)), key=repr)
        return "term-comparison", self.operators, keys

    def render(self) -> str:
        rendered = self.terms[0].render()
        for operator, term in zip(self.operators, self.terms[1:], strict=True):
            rendered += operator + term.render()
        return rendered

    def remap(self, variables: dict[int, int]) -> "TermComparisonConstraint":
        return TermComparisonConstraint(
            tuple(term.remap(variables) for term in self.terms), self.operators
        )
