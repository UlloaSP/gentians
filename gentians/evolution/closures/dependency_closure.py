from __future__ import annotations

import random
import time

from ...rule_generation.program import Program
from ...rule_generation.rule_space import RuleSpace
from .common import bits, defined_predicates, prepare_space
from ...timing import add, current_phase


class DependencyClosure:
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
        self.space = prepare_space(program, space, True)
        self.fixed_size = fixed_size
        self.target_size = min(max_clauses, len(self.space))
        background = defined_predicates(program.background)
        predicates = set(background)
        for entry in self.space.entries:
            predicates.update(entry.heads)
            predicates.update(entry.deps)
        self.predicate_ids = {
            predicate: index
            for index, predicate in enumerate(sorted(predicates))
        }
        self.background_mask = self._predicate_mask(background)
        self.masks = {
            entry.text: (
                self._predicate_mask(entry.heads),
                self._predicate_mask(entry.deps),
                entry.body_literals,
            )
            for entry in self.space.entries
        }
        self.rules_by_head: dict[int, list[str]] = {}
        for rule, (heads, _deps, _body) in self.masks.items():
            for bit in bits(heads):
                self.rules_by_head.setdefault(bit, []).append(rule)

    def sample(self, target_size: int | None = None) -> tuple[str, ...] | None:
        if not self.space:
            return None
        limit = min(self.max_clauses, len(self.space))
        size = (
            limit
            if self.fixed_size
            else max(1, min(target_size or self.rng.randint(1, limit), limit))
        )
        for _ in range(64):
            selected = tuple(self.rng.sample(self.space.clauses, size))
            started = time.perf_counter()
            normalized = self.normalize(selected)
            add(f"{current_phase()}.closure", time.perf_counter() - started)
            if normalized is not None and (
                self.fixed_size or len(normalized) <= size
            ):
                return normalized
        return None

    def normalize(self, proposal: tuple[str, ...]) -> tuple[str, ...] | None:
        candidate = tuple(sorted(dict.fromkeys(proposal)))
        if not candidate or len(candidate) > self.max_clauses:
            return None
        if any(rule not in self.masks for rule in candidate):
            return None
        closed = self._close(list(candidate))
        if closed is None:
            return None
        if self.fixed_size:
            closed = self._fill(closed)
            if closed is None or len(closed) != self.target_size:
                return None
        return tuple(sorted(closed))

    def _close(self, candidate: list[str]) -> list[str] | None:
        closed = list(candidate)
        closed_set = set(closed)
        defined = self.background_mask
        deps = 0
        for rule in closed:
            heads, required, _body = self.masks[rule]
            defined |= heads
            deps |= required
        while missing := deps & ~defined:
            if len(closed) >= self.max_clauses:
                return None
            missing_bit = min(
                bits(missing),
                key=lambda bit: len(self.rules_by_head.get(bit, ())),
            )
            provider = self._provider(missing_bit, missing, defined, closed_set)
            if provider is None:
                return None
            closed.append(provider)
            closed_set.add(provider)
            heads, required, _body = self.masks[provider]
            defined |= heads
            deps |= required
        return closed

    def _fill(self, closed: list[str]) -> list[str] | None:
        while len(closed) < self.target_size:
            added = False
            for rule in sorted(set(self.space.clauses) - set(closed)):
                expanded = self._close([*closed, rule])
                if expanded is not None and len(expanded) <= self.target_size:
                    closed = expanded
                    added = True
                    break
            if not added:
                return None
        return closed

    def _provider(
        self,
        missing_bit: int,
        missing: int,
        defined: int,
        closed: set[str],
    ) -> str | None:
        choices = []
        for rule in self.rules_by_head.get(missing_bit, ()):
            if rule in closed:
                continue
            heads, deps, body = self.masks[rule]
            score = (
                (heads & missing).bit_count(),
                -(deps & ~(defined | heads)).bit_count(),
                -body,
                rule,
            )
            choices.append((score, rule))
        return max(choices)[1] if choices else None

    def _predicate_mask(self, predicates) -> int:
        mask = 0
        for predicate in predicates:
            mask |= 1 << self.predicate_ids[predicate]
        return mask
