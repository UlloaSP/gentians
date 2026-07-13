from typing import Protocol

from ...rule_generation.rule_space import RuleSpace


class Closure(Protocol):
    space: RuleSpace

    def sample(self, target_size: int | None = None) -> tuple[str, ...] | None: ...

    def normalize(self, proposal: tuple[str, ...]) -> tuple[str, ...] | None: ...
