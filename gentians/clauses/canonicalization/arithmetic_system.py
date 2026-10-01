from dataclasses import dataclass

from clingo import ast

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

    def instantiate(self) -> tuple[ast.AST, ...]:
        literals: list[ast.AST] = []
        guard_keys: set[tuple[object, ...]] = set()
        for relation in self.relations:
            node = relation.instantiate()
            if node not in literals:
                literals.append(node)
            if not isinstance(relation, ExpressionConstraint):
                continue
            for key, guard in zip(relation.guard_keys, relation.guard_literals, strict=True):
                if key not in guard_keys:
                    guard_keys.add(key)
                    literals.append(guard)
        return tuple(literals)

    def render(self) -> tuple[str, ...]:
        return tuple(str(node) for node in self.instantiate())

    def remap(self, variables: dict[int, int], width: int) -> "ArithmeticSystem":
        return ArithmeticSystem(
            tuple(
                relation.remap(variables, width)
                if isinstance(relation, LinearConstraint)
                else relation.remap(variables)
                for relation in self.relations
            )
        )
