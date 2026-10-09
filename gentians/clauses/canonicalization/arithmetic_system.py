from dataclasses import dataclass, field
from functools import lru_cache

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
    _key: ArithmeticSystemKey | None = field(default=None, init=False, repr=False, compare=False)
    linear: bool = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        # Repeating an exact comparison in a conjunction adds no ASP meaning.
        # The formatter already removes duplicate native literals; normalize
        # the component recipe before its key instead of storing several keys
        # for that same repetition. Equality includes orientation and safety.
        if len(self.relations) > 1:
            object.__setattr__(self, "relations", tuple(dict.fromkeys(self.relations)))
        object.__setattr__(self, "linear", all(isinstance(relation, LinearConstraint) for relation in self.relations))

    @property
    def key(self) -> ArithmeticSystemKey:
        if self._key is None:
            key = tuple(relation.key for relation in self.relations)
            object.__setattr__(self, "_key", key)
            return key
        return self._key

    @property
    def variables(self) -> frozenset[int]:
        return frozenset().union(*(relation.variables for relation in self.relations))

    @lru_cache(maxsize=8192)
    def instantiate(self) -> tuple[ast.AST, ...]:
        """Bound native syntax retention independently of stored rule recipes."""
        if len(self.relations) == 1 and not isinstance(self.relations[0], ExpressionConstraint):
            result = (self.relations[0].instantiate(),)
            return result
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
