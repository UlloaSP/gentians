from __future__ import annotations

from dataclasses import dataclass
import random

from ..rule_generation.program import Program
from ..rule_generation.rule_space import Predicate, RuleEntry, RuleSpace


@dataclass(frozen=True)
class _RuleMask:
    entry: RuleEntry
    head_mask: int
    dep_mask: int


class ProgramSampler:
    def __init__(self, program: Program, rule_space: RuleSpace) -> None:
        self.rule_space = rule_space
        predicates = _defined_predicates(program.background) | _example_predicates(program)
        for entry in rule_space.entries:
            predicates.update(entry.heads)
            predicates.update(entry.deps)
        self.predicate_bits = {
            predicate: 1 << index for index, predicate in enumerate(sorted(predicates))
        }
        self.background_mask = self._predicate_mask(_defined_predicates(program.background))
        self.example_mask = self._predicate_mask(_example_predicates(program))
        self.masks_by_rule = {
            entry.text: _RuleMask(
                entry,
                self._predicate_mask(entry.heads),
                self._predicate_mask(entry.deps),
            )
            for entry in rule_space.entries
        }
        self.rules_by_head_bit: dict[int, list[str]] = {}
        for mask in self.masks_by_rule.values():
            for bit in _bits(mask.head_mask):
                self.rules_by_head_bit.setdefault(bit, []).append(mask.entry.text)

    def sample(
        self,
        max_program_clauses: int,
        known_signatures: set[tuple[str, ...]] | None = None,
        preferred_rules: list[str] | None = None,
    ) -> list[str] | None:
        pool = preferred_rules or self.rule_space.clauses
        if not pool:
            return None
        limit = max(1, min(max_program_clauses, len(self.rule_space)))
        known = known_signatures or set()
        for _ in range(64):
            target_size = random.randint(1, limit)
            program = [random.choice(pool)]
            closed = self.repair(program, limit, preferred_rules=pool)
            while closed is not None and len(closed) < target_size:
                available = [rule for rule in pool if rule not in closed]
                if not available:
                    break
                next_program = [*closed, random.choice(available)]
                next_closed = self.repair(next_program, limit, preferred_rules=pool)
                if next_closed is None:
                    break
                closed = next_closed
            if closed is not None and tuple(closed) not in known:
                return closed
        return None

    def repair(
        self,
        program: list[str],
        max_program_clauses: int,
        preferred_rules: list[str] | None = None,
    ) -> list[str] | None:
        repaired = sorted(dict.fromkeys(program))
        preferred = set(preferred_rules or [])
        while True:
            missing = self._missing_mask(repaired)
            if not missing:
                return repaired
            if len(repaired) >= max_program_clauses:
                return None
            missing_bit = min(
                _bits(missing),
                key=lambda bit: len(self.rules_by_head_bit.get(bit, ())),
            )
            candidates = [
                rule
                for rule in self.rules_by_head_bit.get(missing_bit, [])
                if rule not in repaired
            ]
            if not candidates:
                return None
            candidates.sort(
                key=lambda rule: self._support_score(
                    rule,
                    missing,
                    repaired,
                    preferred,
                ),
                reverse=True,
            )
            repaired.append(candidates[0])
            repaired.sort()

    def is_closed(self, program: list[str]) -> bool:
        return self._missing_mask(program) == 0

    def _missing_mask(self, program: list[str]) -> int:
        defined, deps = self._program_masks(program)
        return deps & ~defined

    def _program_masks(self, program: list[str]) -> tuple[int, int]:
        defined = self.background_mask
        deps = self.example_mask
        for rule in program:
            mask = self.masks_by_rule.get(rule)
            if mask is None:
                continue
            defined |= mask.head_mask
            deps |= mask.dep_mask
        return defined, deps

    def _support_score(
        self,
        rule: str,
        missing: int,
        program: list[str],
        preferred: set[str],
    ) -> tuple[int, int, int, float]:
        mask = self.masks_by_rule[rule]
        defined, _ = self._program_masks(program)
        resolved = (mask.head_mask & missing).bit_count()
        introduced = (mask.dep_mask & ~(defined | mask.head_mask)).bit_count()
        preferred_bonus = int(rule in preferred)
        return (
            preferred_bonus,
            resolved,
            -introduced,
            -mask.entry.body_literals + random.random(),
        )

    def _predicate_mask(self, predicates: set[Predicate] | frozenset[Predicate]) -> int:
        mask = 0
        for predicate in predicates:
            mask |= self.predicate_bits[predicate]
        return mask


def _defined_predicates(lines: list[str]) -> set[Predicate]:
    defined: set[Predicate] = set()
    for entry in RuleSpace.from_clauses(lines).entries:
        defined.update(entry.heads)
    return defined


def _example_predicates(program: Program) -> set[Predicate]:
    deps: set[Predicate] = set()
    for example in [*program.positive_examples, *program.negative_examples]:
        for fragment in (example.included, example.excluded, example.context):
            deps.update(_fragment_predicates(fragment))
    return deps


def _fragment_predicates(fragment: str) -> set[Predicate]:
    fragment = fragment.strip()
    if not fragment:
        return set()
    if not fragment.endswith("."):
        fragment = f":- {fragment}."
    entry = RuleSpace.from_clauses([fragment]).entries[0]
    return set(entry.heads | entry.deps)


def _bits(mask: int):
    while mask:
        bit = mask & -mask
        yield bit
        mask ^= bit
