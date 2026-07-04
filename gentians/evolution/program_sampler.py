from __future__ import annotations

from dataclasses import dataclass
import os
import random

from ..rule_generation.program import Program
from ..rule_generation.parser import clause_predicates
from ..rule_generation.rule_space import Predicate, RuleEntry, RuleSpace


@dataclass(frozen=True, slots=True)
class _RuleMask:
    entry: RuleEntry
    head_mask: int
    dep_mask: int


class ProgramSampler:
    def __init__(self, program: Program, rule_space: RuleSpace) -> None:
        background_predicates = _defined_predicates(program.background)
        example_predicates = _example_predicates(program)
        entries = _prune_uncloseable_rules(
            rule_space.entries,
            background_predicates,
        )
        self.rule_space = RuleSpace(entries)
        predicates = background_predicates | example_predicates
        for entry in self.rule_space.entries:
            predicates.update(entry.heads)
            predicates.update(entry.deps)
        self.predicate_ids = {
            predicate: index for index, predicate in enumerate(sorted(predicates))
        }
        self.background_mask = self._predicate_mask(background_predicates)
        self.example_mask = self._predicate_mask(example_predicates)
        self.masks_by_rule = {
            entry.text: _RuleMask(
                entry,
                self._predicate_mask(entry.heads),
                self._predicate_mask(entry.deps),
            )
            for entry in self.rule_space.entries
        }
        self._close_cache: dict[tuple[tuple[str, ...], int], tuple[str, ...] | None] = {}
        self.rules_by_head_bit: dict[int, list[str]] = {}
        for mask in self.masks_by_rule.values():
            for bit in _bits(mask.head_mask):
                self.rules_by_head_bit.setdefault(bit, []).append(mask.entry.text)
        for rules in self.rules_by_head_bit.values():
            rules.sort(key=self._provider_order_key)

    def closed_program(
        self,
        max_program_clauses: int,
        *,
        target_size: int | None = None,
        forced_rules: tuple[str, ...] | None = None,
        known_signatures: set[tuple[str, ...]] | None = None,
        extra_forbidden_signatures: set[tuple[str, ...]] | None = None,
    ) -> tuple[str, ...] | None:
        if not self.rule_space:
            return None
        forced = tuple(sorted(dict.fromkeys(forced_rules or ())))
        if any(rule not in self.masks_by_rule for rule in forced):
            return None
        limit = max(1, min(max_program_clauses, len(self.rule_space)))
        known = known_signatures or set()
        extra_forbidden = extra_forbidden_signatures or ()
        if forced:
            closed = self._close(forced, limit)
            if (
                closed is None
                or (target_size is not None and len(closed) > target_size)
                or closed in known
                or closed in extra_forbidden
            ):
                return None
            return closed

        for _ in range(64):
            size_limit = max(1, min(target_size or random.randint(1, limit), limit))
            program = (random.choice(self.rule_space.clauses),)
            closed = self._close(program, limit)
            if closed is not None and len(closed) > size_limit:
                closed = None
            closed_set = set(closed) if closed is not None else set()
            while closed is not None and len(closed) < size_limit:
                rule = _random_rule_outside(self.rule_space.clauses, closed_set)
                if rule is None:
                    break
                closed = tuple(sorted((*closed, rule)))
                closed_set.add(rule)
                closed = self._close(closed, limit)
                if closed is not None and len(closed) > size_limit:
                    closed = None
                else:
                    closed_set = set(closed) if closed is not None else set()
            if closed is not None:
                if closed not in known and closed not in extra_forbidden:
                    return closed
        return None

    def _close(self, program: tuple[str, ...], max_program_clauses: int) -> tuple[str, ...] | None:
        key = (program, max_program_clauses)
        if key in self._close_cache:
            return self._close_cache[key]
        closed = list(program)
        closed_set = set(closed)
        defined, deps = self._program_masks(closed)
        while True:
            missing = deps & ~defined
            if not missing:
                closed.sort()
                result = tuple(closed)
                self._close_cache[key] = result
                if os.environ.get("GENTIANS_AUDIT_PROGRAM_SAMPLER_ASP"):
                    _assert_asp_closed_agrees(closed, self.background_mask, self.example_mask, self.masks_by_rule)
                return result
            if len(closed) >= max_program_clauses:
                self._close_cache[key] = None
                return None
            missing_bit = min(
                _bits(missing),
                key=lambda bit: len(self.rules_by_head_bit.get(bit, ())),
            )
            rule = self._best_repair_candidate(missing_bit, missing, defined, closed_set)
            if rule is None:
                self._close_cache[key] = None
                return None
            closed.append(rule)
            closed_set.add(rule)
            mask = self.masks_by_rule[rule]
            defined |= mask.head_mask
            deps |= mask.dep_mask

    def _program_masks(self, program: tuple[str, ...] | list[str]) -> tuple[int, int]:
        defined = self.background_mask
        deps = self.example_mask
        for rule in program:
            mask = self.masks_by_rule.get(rule)
            if mask is None:
                continue
            defined |= mask.head_mask
            deps |= mask.dep_mask
        return defined, deps

    def _best_repair_candidate(
        self,
        missing_bit: int,
        missing: int,
        defined: int,
        closed: set[str],
    ) -> str | None:
        best_rule: str | None = None
        best_score: tuple[int, int, float] | None = None
        for rule in self.rules_by_head_bit.get(missing_bit, ()):
            if rule in closed:
                continue
            mask = self.masks_by_rule[rule]
            resolved = (mask.head_mask & missing).bit_count()
            introduced = (mask.dep_mask & ~(defined | mask.head_mask)).bit_count()
            score = (resolved, -introduced, -mask.entry.body_literals)
            if best_score is None or score > best_score:
                best_rule = rule
                best_score = score
        return best_rule

    def _provider_order_key(self, rule: str) -> tuple[int, int, str]:
        mask = self.masks_by_rule[rule]
        return (mask.dep_mask.bit_count(), mask.entry.body_literals, rule)

    def _predicate_mask(self, predicates: set[Predicate] | frozenset[Predicate]) -> int:
        mask = 0
        for predicate in predicates:
            mask |= 1 << self.predicate_ids[predicate]
        return mask


def _defined_predicates(lines: list[str]) -> set[Predicate]:
    defined: set[Predicate] = set()
    for entry in RuleSpace.from_clauses(lines).entries:
        defined.update(entry.heads)
    return defined


def _prune_uncloseable_rules(
    entries: tuple[RuleEntry, ...],
    background_predicates: set[Predicate],
) -> list[RuleEntry]:
    kept = list(entries)
    while True:
        providers = set(background_predicates)
        for entry in kept:
            providers.update(entry.heads)
        next_kept = [entry for entry in kept if entry.deps <= providers]
        if len(next_kept) == len(kept):
            return kept
        kept = next_kept


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
    heads, deps, _ = clause_predicates(fragment)
    return set(heads | deps)


def _random_rule_outside(pool: tuple[str, ...], current: set[str]) -> str | None:
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


def _bits(mask: int):
    while mask:
        bit = mask & -mask
        yield bit
        mask ^= bit


def _assert_asp_closed_agrees(
    program: list[str],
    background_mask: int,
    example_mask: int,
    masks_by_rule: dict[str, _RuleMask],
) -> None:
    import clingo

    defined = background_mask
    needed = example_mask
    for rule in program:
        mask = masks_by_rule[rule]
        defined |= mask.head_mask
        needed |= mask.dep_mask
    facts = []
    for bit in _bits(defined):
        facts.append(f"defined({bit}).")
    for bit in _bits(needed):
        facts.append(f"needed({bit}).")
    facts.append(":- needed(P), not defined(P).")
    ctl = clingo.Control()
    ctl.add("base", [], "\n".join(facts))
    ctl.ground([("base", [])])
    result = ctl.solve()
    if not result.satisfiable:
        raise AssertionError("ASP audit disagrees with Python program closure")
