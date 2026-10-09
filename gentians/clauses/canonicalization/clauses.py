from collections.abc import Iterator
from functools import lru_cache

from ...language.asp import Predicate
from ..clause import Clause
from ..clause_mode import ClauseMode
from ..mode_metadata import ModeMetadata
from ..metadata import ClauseMetadata
from ..recipes import RuleRecipes
from ..packed_recipe import PackedRecipe
from ..reified_clause import ReifiedClause
from ..reified_literal import ReifiedLiteral
from .arithmetic import _ArithmeticSystemsCache, _component_recipe, _literal_traits, canonical_arithmetic_clause
from .arithmetic_system import ArithmeticSystemKey
from .canonical_clause import CanonicalArithmeticClause


class ClauseCanonicalizer:
    """Retain the globally preferred representative of each canonical rule."""

    def __init__(self, modes: dict[int, ClauseMode], max_variables: int, *, pack: bool = False) -> None:
        self.modes = modes
        self.max_variables = max_variables
        self.representatives: dict[ArithmeticSystemKey, tuple[str, CanonicalArithmeticClause | PackedRecipe, tuple[int, ClauseMetadata]] | None] = {}
        self.systems_cache = _ArithmeticSystemsCache()
        self.has_builtins = any(mode.section == "body" and mode.builtin for mode in modes.values())
        self.metadata = ModeMetadata(modes)
        self.recipes = RuleRecipes(modes)
        self.pack = pack
        # Traits depend on a mode and its bindings, never the occurrence slot.
        self._traits = lru_cache(maxsize=8192)(
            lambda mode, variables: _literal_traits(ReifiedLiteral("body", 0, mode, variables), modes)
        )
        self.literal_traits = lambda literal: self._traits(literal.mode_id, literal.variables)

        @lru_cache(maxsize=8192)
        def head_context(head):
            external = numeric = 0
            for literal in head:
                external |= literal.variable_mask
                numeric |= self.literal_traits(literal)[2]
            return external, numeric

        self.head_context = head_context
        self.components = lru_cache(maxsize=8192)(
            lambda bindings, external, safe, numeric: _component_recipe(
                tuple(ReifiedLiteral("body", slot, mode, variables)
                      for slot, (mode, variables) in enumerate(bindings)),
                modes, external, safe, numeric, max_variables
            )
        )

    def add(self, clause: ReifiedClause) -> None:
        if self.has_builtins:
            canonical = canonical_arithmetic_clause(
                clause, self.modes, self.max_variables, self.systems_cache, self.literal_traits, self.components,
                self.head_context,
            )
            if canonical is None:
                return
            key = canonical.key
        else:
            key = (tuple(literal.key for literal in clause.head),
                   tuple(literal.key for literal in clause.body), ())
            canonical = None
        current = self.representatives.get(key)
        if current is None:
            if canonical is None:
                canonical = CanonicalArithmeticClause(clause.head, clause.body, ())
            rendered = self.recipes.render(canonical)
            self.representatives[key] = rendered, self.recipes.pack(canonical) if self.pack else canonical, self._source(clause)
        elif len(clause.body) > current[2][0]:
            return
        elif canonical is None or all(system.linear for system in canonical.systems):
            if len(clause.body) < current[2][0]:
                self.representatives[key] = current[0], current[1], self._source(clause)
        else:
            # Semantic keys deliberately normalize expressions/orientation.
            # Exact relation equality additionally preserves output safety,
            # operand trees and guards. Only identical syntax may reuse text.
            same_syntax = all(
                left.relations == right.relations
                for left, right in zip(canonical.systems, current[1].systems, strict=True)
            )
            if same_syntax:
                if len(clause.body) < current[2][0]:
                    self.representatives[key] = current[0], current[1], self._source(clause)
                return
            rendered = self.recipes.render(canonical)
            if (len(clause.body), rendered) < (
                current[2][0],
                current[0],
            ):
                self.representatives[key] = rendered, self.recipes.pack(canonical) if self.pack else canonical, self._source(clause)

    def _source(self, clause):
        return len(clause.body), self.metadata.for_modes(
            tuple(literal.mode_id for literal in clause.head), tuple(literal.mode_id for literal in clause.body),
        )

    def finish(self) -> Iterator[Clause]:
        # ClauseSpace owns final text deduplication and deterministic ordering.
        # Preserve insertion order (including textual ties), while transferring
        # values out of the canonical index. Replacing values does not resize
        # the dictionary or invalidate its iterator.
        representatives = self.representatives
        try:
            for key, current in representatives.items():
                if current is None:
                    continue
                rendered, canonical, (_raw_count, metadata) = current
                entry = Clause(rendered, canonical, metadata, self.recipes)
                representatives[key] = None
                yield entry
        finally:
            representatives.clear()


def _clause_metadata(
    head: tuple[int, ...],
    body: tuple[int, ...],
    modes: dict[int, ClauseMode],
) -> tuple[frozenset[Predicate], frozenset[Predicate], int]:
    """Providers, dependencies and body cost depend on modes, not bindings."""
    heads: set[Predicate] = set()
    deps: set[Predicate] = set()
    body_literals = len(body)
    for mode_id in head:
        mode = modes[mode_id]
        heads.update(mode.head_predicates)
        deps.update(mode.head_dependencies)
        body_literals += mode.condition_count
    for mode_id in body:
        mode = modes[mode_id]
        deps.update(mode.dependencies)
        body_literals += mode.condition_count
    return frozenset(heads), frozenset(deps), body_literals
