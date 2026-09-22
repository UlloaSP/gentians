from dataclasses import dataclass

from .comparison_constraint import ComparisonConstraint
from .expression_constraint import ExpressionConstraint
from .linear_constraint import LinearConstraint
from .term_comparison_constraint import TermComparisonConstraint

ArithmeticSystemKey = tuple[object, ...]


SystemRelation = (
    LinearConstraint
    | ExpressionConstraint
    | ComparisonConstraint
    | TermComparisonConstraint
)


@dataclass(frozen=True, slots=True)
class ArithmeticSystem:
    relations: tuple[SystemRelation, ...]

    @property
    def key(self) -> ArithmeticSystemKey:
        return tuple(relation.key for relation in self.relations)

    @property
    def variables(self) -> frozenset[int]:
        return frozenset().union(*(relation.variables for relation in self.relations))

    def render(self) -> tuple[str, ...]:
        rendered: list[str] = []
        rendered_guard_keys: set[tuple[object, ...]] = set()
        for relation in self.relations:
            value = relation.render()
            if value not in rendered:
                rendered.append(value)
            if not isinstance(relation, ExpressionConstraint):
                continue
            for key, guard in zip(
                relation.guard_keys, relation.rendered_guards, strict=True
            ):
                if key not in rendered_guard_keys:
                    rendered_guard_keys.add(key)
                    rendered.append(guard)
        return tuple(rendered)

    def remap(self, variables: dict[int, int], width: int) -> "ArithmeticSystem":
        return ArithmeticSystem(
            tuple(
                relation.remap(variables, width)
                if isinstance(relation, LinearConstraint)
                else relation.remap(variables)
                for relation in self.relations
            )
        )
