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
            closed = self.repair(program, limit, preferred_rules=preferred_rules)
            while closed is not None and len(closed) < target_size:
                rule = self._random_rule_outside(pool, set(closed))
                if rule is None:
                    break
                next_program = [*closed, rule]
                next_closed = self.repair(
                    next_program,
                    limit,
                    preferred_rules=preferred_rules,
                )
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
        repaired_set = set(repaired)
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
            defined, _ = self._program_masks(repaired)
            best = self._best_repair_candidate(
                missing_bit,
                missing,
                defined,
                preferred,
                repaired_set,
            )
            if best is None:
                return None
            repaired.append(best)
            repaired_set.add(best)
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
        defined: int,
        preferred: set[str],
    ) -> tuple[int, int, int, float]:
        mask = self.masks_by_rule[rule]
        resolved = (mask.head_mask & missing).bit_count()
        introduced = (mask.dep_mask & ~(defined | mask.head_mask)).bit_count()
        preferred_bonus = int(rule in preferred)
        return (
            preferred_bonus,
            resolved,
            -introduced,
            -mask.entry.body_literals + random.random(),
        )

    def _best_repair_candidate(
        self,
        missing_bit: int,
        missing: int,
        defined: int,
        preferred: set[str],
        repaired: set[str],
    ) -> str | None:
        best_rule: str | None = None
        best_score: tuple[int, int, int, float] | None = None
        for rule in preferred:
            mask = self.masks_by_rule.get(rule)
            if rule in repaired or mask is None or not mask.head_mask & missing_bit:
                continue
            score = self._support_score(rule, missing, defined, preferred)
            if best_score is None or score > best_score:
                best_rule = rule
                best_score = score
        if best_rule is not None:
            return best_rule
        for rule in self.rules_by_head_bit.get(missing_bit, ()):
            if rule in repaired:
                continue
            score = self._support_score(rule, missing, defined, preferred)
            if best_score is None or score > best_score:
                best_rule = rule
                best_score = score
        return best_rule

    def _random_rule_outside(self, pool: list[str], current: set[str]) -> str | None:
        for _ in range(min(len(pool), 8)):
            rule = random.choice(pool)
            if rule not in current:
                return rule
        start = random.randrange(len(pool))
        for offset in range(len(pool)):
            rule = pool[(start + offset) % len(pool)]
            if rule not in current:
                return rule
        return None

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
