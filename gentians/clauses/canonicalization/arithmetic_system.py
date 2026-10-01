from dataclasses import dataclass, field

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
    _literals: tuple[ast.AST, ...] | None = field(
        default=None, init=False, repr=False, compare=False,
    )

    @property
    def key(self) -> ArithmeticSystemKey:
        return tuple(relation.key for relation in self.relations)

    @property
    def variables(self) -> frozenset[int]:
        return frozenset().union(*(relation.variables for relation in self.relations))

    def instantiate(self) -> tuple[ast.AST, ...]:
        """Share native syntax for this immutable system; callers use AST.update."""
        if self._literals is not None:
            return self._literals
        literals: list[ast.AST] = []
        seen: set[ast.AST] = set()
        guard_keys: set[tuple[object, ...]] = set()
        for relation in self.relations:
            node = relation.instantiate()
            if node not in seen:
                seen.add(node)
                literals.append(node)
            if not isinstance(relation, ExpressionConstraint):
                continue
            for key, guard in zip(relation.guard_keys, relation.guard_literals, strict=True):
                if key not in guard_keys:
                    guard_keys.add(key)
                    seen.add(guard)
                    literals.append(guard)
        result = tuple(literals)
        object.__setattr__(self, "_literals", result)
        return result

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
