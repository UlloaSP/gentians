from __future__ import annotations

import random

from ...rule_generation.parser import fragment_atoms
from ...rule_generation.program import Program
from ...rule_generation.rule_space import RuleSpace
from ..types import Genome
from .common import (
    bits,
    defined_predicates,
    mixed_rules,
    prepare_space,
    record_generation_time,
)


class ProgramGenerator:
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
        self.space = prepare_space(program, space)
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
        self.invented_mask = self._predicate_mask(set(program.invented_predicates))
        target_predicates = {
            (name, len(arguments))
            for example in [*program.positive_examples, *program.negative_examples]
            for fragment in (example.included, example.excluded)
            for name, arguments, _negative in fragment_atoms(fragment)
        }
        self.target_mask = self._predicate_mask(target_predicates)
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

    @record_generation_time
    def create(self, target_size: int | None = None) -> Genome | None:
        if not self.space:
            return None
        limit = min(self.max_clauses, len(self.space))
        size = (
            limit
            if self.fixed_size
            else max(1, min(target_size or self.rng.randint(1, limit), limit))
        )
        for _ in range(64):
            candidate = self._build(self._sample_rules(size))
            if candidate is not None and (self.fixed_size or len(candidate) <= size):
                return candidate
        return None

    @record_generation_time
    def append(self, program: Genome, rule: str) -> Genome | None:
        if rule in program or rule not in self.masks or self.fixed_size:
            return None
        candidate = self._build((*program, rule))
        return candidate if candidate != program else None

    @record_generation_time
    def remove(self, program: Genome, rule: str) -> Genome | None:
        if rule not in program or len(program) == 1:
            return None
        candidate = self._build(
            tuple(item for item in program if item != rule), forbidden={rule}
        )
        return candidate if candidate != program else None

    @record_generation_time
    def replace(
        self, program: Genome, source: str, replacement: str
    ) -> Genome | None:
        if (
            source not in program
            or replacement not in self.masks
            or replacement in program
        ):
            return None
        proposal = tuple(
            replacement if rule == source else rule for rule in program
        )
        candidate = self._build(proposal, forbidden={source})
        return candidate if candidate != program else None

    @record_generation_time
    def mix(
        self,
        first: Genome,
        second: Genome,
        first_probability: float,
        second_probability: float,
    ) -> Genome | None:
        preferred = mixed_rules(
            first,
            second,
            first_probability,
            second_probability,
            self.rng,
        )
        selected: tuple[str, ...] = ()
        limit = self.target_size if self.fixed_size else self.max_clauses
        for rule in preferred:
            if rule in selected:
                continue
            expanded = self._complete([*selected, rule], set())
            if expanded is not None and len(expanded) <= limit:
                selected = tuple(sorted(expanded))
        if not selected:
            return None
        return self._fill(list(selected), set()) if self.fixed_size else selected

    def _sample_rules(self, size: int) -> tuple[str, ...]:
        target_rules = [
            rule
            for rule, (heads, _deps, _body) in self.masks.items()
            if heads & self.target_mask
        ]
        if not self.invented_mask or not target_rules:
            return tuple(self.rng.sample(self.space.clauses, size))
        invented_consumers = [
            rule
            for rule in target_rules
            if self.masks[rule][1] & self.invented_mask
        ]
        if invented_consumers:
            target_rules = invented_consumers
        seed = self.rng.choice(target_rules)
        if self.fixed_size:
            return (seed,)
        available = [rule for rule in self.space.clauses if rule != seed]
        return (seed, *self.rng.sample(available, min(size - 1, len(available))))

    def _build(
        self, proposal: tuple[str, ...], forbidden: set[str] | None = None
    ) -> Genome | None:
        blocked = forbidden or set()
        candidate = tuple(sorted(dict.fromkeys(proposal)))
        if (
            not candidate
            or len(candidate) > self.max_clauses
            or any(rule not in self.masks or rule in blocked for rule in candidate)
        ):
            return None
        completed = self._complete(list(candidate), blocked)
        if completed is None:
            return None
        if self.fixed_size:
            return self._fill(completed, blocked)
        return tuple(sorted(completed))

    def _complete(
        self, candidate: list[str], forbidden: set[str]
    ) -> list[str] | None:
        completed = list(candidate)
        completed_set = set(completed)
        defined = self.background_mask
        deps = 0
        for rule in completed:
            heads, required, _body = self.masks[rule]
            defined |= heads
            deps |= required
        while missing := deps & ~defined:
            if len(completed) >= self.max_clauses:
                return None
            missing_bit = min(
                bits(missing),
                key=lambda bit: len(self.rules_by_head.get(bit, ())),
            )
            provider = self._provider(
                missing_bit, missing, defined, completed_set, forbidden
            )
            if provider is None:
                return None
            completed.append(provider)
            completed_set.add(provider)
            heads, required, _body = self.masks[provider]
            defined |= heads
            deps |= required
        return completed

    def _fill(self, completed: list[str] | Genome, forbidden: set[str]) -> Genome | None:
        candidate = list(completed)
        if len(candidate) > self.target_size:
            return None
        while len(candidate) < self.target_size:
            choices = []
            defined, active_deps = self._program_masks(candidate)
            for rule in sorted(set(self.space.clauses) - set(candidate) - forbidden):
                expanded = self._complete([*candidate, rule], forbidden)
                if expanded is not None and len(expanded) <= self.target_size:
                    heads, deps, body = self.masks[rule]
                    score = (
                        (heads & active_deps & self.invented_mask).bit_count(),
                        int(bool(heads)),
                        -(deps & ~(defined | heads)).bit_count(),
                        -body,
                    )
                    choices.append((score, expanded))
            if not choices:
                return None
            best_score = max(score for score, _expanded in choices)
            candidate = self.rng.choice(
                [expanded for score, expanded in choices if score == best_score]
            )
        return tuple(sorted(candidate))

    def _provider(
        self,
        missing_bit: int,
        missing: int,
        defined: int,
        present: set[str],
        forbidden: set[str],
    ) -> str | None:
        choices = []
        for rule in self.rules_by_head.get(missing_bit, ()):
            if rule in present or rule in forbidden:
                continue
            heads, deps, body = self.masks[rule]
            if missing_bit & self.invented_mask and missing_bit & deps:
                continue
            score = (
                (heads & missing).bit_count(),
                -(deps & ~(defined | heads)).bit_count(),
                -body,
            )
            choices.append((score, rule))
        if not choices:
            return None
        best_score = max(score for score, _rule in choices)
        return self.rng.choice([rule for score, rule in choices if score == best_score])

    def _program_masks(self, rules: list[str]) -> tuple[int, int]:
        defined = self.background_mask
        deps = 0
        for rule in rules:
            heads, required, _body = self.masks[rule]
            defined |= heads
            deps |= required
        return defined, deps

    def _predicate_mask(self, predicates) -> int:
        mask = 0
        for predicate in predicates:
            identifier = self.predicate_ids.get(predicate)
            if identifier is not None:
                mask |= 1 << identifier
        return mask
