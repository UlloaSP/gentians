from __future__ import annotations

import random
import time

from ...rule_generation.program import Program
from ...rule_generation.rule_space import RuleSpace
from .common import prepare_space
from ...timing import add, current_phase


class NoClosure:
    def __init__(
        self,
        program: Program,
        space: RuleSpace,
        max_clauses: int,
        rng: random.Random,
        fixed_size: bool = False,
    ) -> None:
        self.max_clauses = max_clauses
        self.rng = rng
        self.space = prepare_space(program, space, False)
        self.rules = set(self.space.clauses)
        self.fixed_size = fixed_size
        self.target_size = min(max_clauses, len(self.space))

    def sample(self, target_size: int | None = None) -> tuple[str, ...] | None:
        if not self.space:
            return None
        limit = min(self.max_clauses, len(self.space))
        size = (
            limit
            if self.fixed_size
            else max(1, min(target_size or self.rng.randint(1, limit), limit))
        )
        proposal = tuple(self.rng.sample(self.space.clauses, size))
        started = time.perf_counter()
        normalized = self.normalize(proposal)
        add(f"{current_phase()}.closure", time.perf_counter() - started)
        return normalized

    def normalize(self, proposal: tuple[str, ...]) -> tuple[str, ...] | None:
        candidate = tuple(sorted(dict.fromkeys(proposal)))
        if not candidate or len(candidate) > self.max_clauses:
            return None
        if any(rule not in self.rules for rule in candidate):
            return None
        if self.fixed_size and len(candidate) < self.target_size:
            missing = self.target_size - len(candidate)
            available = sorted(self.rules - set(candidate))
            if len(available) < missing:
                return None
            candidate = tuple(sorted((*candidate, *available[:missing])))
        if self.fixed_size and len(candidate) != self.target_size:
            return None
        return candidate
