"""Exact specialization for independent, unary output-only constraints."""

from collections.abc import Iterable
from dataclasses import fields
from itertools import combinations, batched
from array import array

import clingo
from clingo.configuration import Configuration
from typing import cast
from ..timing import add, metric_enabled, is_enabled, net_time, instrumentation, record_metric
from ..clingo_stats import clingo_statistics

from ..language import terms
from ..language.ir.atom_literal import AtomLiteral
from .analysis.properties import ClosedWorldProperties
from .canonicalization.canonical_clause import CanonicalArithmeticClause
from .clause import Clause
from .clause_mode import ClauseMode
from .clause_space import ClauseSpace
from .mode_metadata import ModeMetadata
from .recipes import RuleRecipes
from .reified_literal import ReifiedLiteral
from .packed_recipe import PackedRecipe


def independent_unary(modes: list[ClauseMode], max_variables: int,
                      properties: ClosedWorldProperties) -> bool:
    if not modes or max_variables < 1:
        return False
    # Every other property can remove subsets, including properties inferred
    # from equal unary extensions. Numeric sign facts have no consumer here.
    if any(getattr(properties, f.name) for f in fields(properties)
           if f.name not in {"positive_args", "nonnegative_args"}):
        return False
    predicates = set()
    groups = set()
    types = set()
    labels = set()
    for mode in modes:
        literal = mode.literal
        if (mode.recall != 1
                or not isinstance(literal, AtomLiteral)
                or literal.default_negated or literal.double_negated
                or literal.atom.signature[0].startswith("-")
                or literal.atom.alternatives or len(literal.atom.terms) != 1
                or terms.kind(literal.atom.terms[0]) != "variable"
                or len(mode.bindings) != 1 or mode.guard_terms or mode.condition_count):
            return False
        if mode.section == "head":
            if mode.head is None or mode.head.kind != "normal" or mode.bindings[0].direction not in {"input", "any"}:
                return False
        elif mode.bindings[0].direction != "output":
            return False
        predicates.add(literal.atom.signature)
        groups.add(mode.recall_group)
        types.add(mode.bindings[0].type)
        if mode.bindings[0].label:
            labels.add(mode.bindings[0].label)
    # Unary literals form one linked global variable; density names it V0 even
    # with a larger #maxv. A positive body supplies head safety. Distinct
    # predicates and the property guard exclude interactions between subsets.
    return (any(mode.section == "body" for mode in modes)
            and len(predicates) == len(modes) == len(groups) and len(types) == 1 and len(labels) <= 1)


def subset_program(modes: list[ClauseMode], limit: int) -> str:
    return "\n".join([
        *(f"mode({mode.id})." for mode in modes),
        f"1 {{ pick(M): mode(M) }} {limit}.",
        "#show pick/1.",
    ])


def _subset_from_model(model) -> tuple[int, ...]:
    return tuple(sorted(symbol.arguments[0].number for symbol in model.symbols(shown=True)))


class SubsetClauses:
    def __init__(self, modes: list[ClauseMode], limit: int, prune_constraints: bool = False, head_limit: int = 1):
        self.modes = {mode.id: mode for mode in modes}
        self.ids = tuple(sorted(mode.id for mode in modes if mode.section == "body"))
        self.forms = (() if prune_constraints else ((),)) + tuple(
            (ReifiedLiteral("head", 0, mode.id, (0,)),) for mode in modes if mode.section == "head" and head_limit
        )
        self.limit = min(limit, len(self.ids))
        self.metadata = ModeMetadata(self.modes)
        self.recipes = RuleRecipes(self.modes)
        self.masks = {mode: self.metadata.bodies[mode][0] for mode in self.ids}
        # A literal is immutable. Sharing its slot/binding recipe retains no AST.
        self.literals = {(slot, mode): ReifiedLiteral("body", slot, mode, (0,))
                         for slot in range(self.limit) for mode in self.ids}

    def recipe(self, ids: tuple[int, ...], head=()):
        body = tuple(self.literals[slot, mode] for slot, mode in enumerate(ids))
        return CanonicalArithmeticClause(head, body, ())

    def entry(self, ids: tuple[int, ...], head=(), *, pack: bool = False) -> Clause:
        recipe = self.recipe(ids, head)
        text = self.recipes.render(recipe)
        # Distinct signed predicates were proved by the specialization guard.
        # Disjoint masks can be added directly without a prefix cache per subset.
        head_mask = self.metadata.heads[head[0].mode_id][0] if head else 0
        metadata = self.metadata.from_masks(head_mask, sum(self.masks[mode] for mode in ids), len(ids))
        return Clause(text, self.recipes.pack(recipe) if pack else recipe, metadata, self.recipes)

    def combinations(self) -> Iterable[tuple[int, ...]]:
        for size in range(1, self.limit + 1):
            yield from combinations(self.ids, size)

    def space(self, engine: str, arguments: list[str], *, pack: bool = True) -> ClauseSpace:
        index: dict[str, Clause] = {}
        if engine == "direct":
            add("clause_generation.grounding", 0.0)
            add("clause_generation.solving", 0.0)
            native_packed = pack and self.recipes.builder.renderer is not None
            codes = {mode: array("I", [self.recipes.pool_index(self.literals[0, mode])]).tobytes()
                     for mode in self.ids} if native_packed and self.limit else {}
            for choices in batched(self.combinations(), 128):
                for head in self.forms:
                    if native_packed:
                        head_pair = self.recipes.head_pair(head)
                        # Keep every owner alive across the batched native call,
                        # including cache evictions in exceptionally long bodies.
                        bodies = tuple(tuple(self.recipes.literal_pair(mode, (0,)) for mode in ids)
                                       for ids in choices)
                        texts = self.recipes.builder.render_parts(tuple(
                            (head_pair[1], tuple(pair[1] for pair in body)) for body in bodies))
                        head_codes = array("I", [self.recipes.pool_index(literal) for literal in head]).tobytes()
                        recipes = (PackedRecipe(head_codes + b"".join(codes[mode] for mode in ids), len(head), ())
                                   for ids in choices)
                    else:
                        recipes = tuple(self.recipe(ids, head) for ids in choices)
                        texts = self.recipes.render_many(recipes)
                    head_mask = self.metadata.heads[head[0].mode_id][0] if head else 0
                    for ids, recipe, text in zip(choices, recipes, texts, strict=True):
                        metadata = self.metadata.from_masks(head_mask, sum(self.masks[mode] for mode in ids), len(ids))
                        index[text] = Clause(text, self.recipes.pack(recipe) if pack else recipe, metadata, self.recipes)
        elif self.limit:
            ctl = clingo.Control(arguments)
            cast(Configuration, ctl.configuration.solve).models = "0"
            program = subset_program([self.modes[mode] for mode in self.ids], self.limit)
            ctl.add("base", [], program)
            measure = is_enabled() or metric_enabled("clingo")
            started = net_time() if measure else 0.0
            ctl.ground([("base", [])])
            grounding = net_time() - started if measure else 0.0
            add("clause_generation.grounding", grounding)
            callback = 0.0

            def collect(model):
                nonlocal callback
                started = net_time() if measure else 0.0
                ids = _subset_from_model(model)
                for head in self.forms:
                    entry = self.entry(ids, head, pack=pack)
                    index[entry.text] = entry
                callback += net_time() - started if measure else 0.0

            started = net_time() if measure else 0.0
            ctl.solve(on_model=collect)
            solving = net_time() - started - callback if measure else 0.0
            add("clause_generation.solving", solving)
            if metric_enabled("clingo"):
                with instrumentation():
                    stats = clingo_statistics(ctl)
                    record_metric("clingo", {"operation_category": "grounding", "phase_context": "clause_generation",
                                             "seconds": grounding, "program_size": 1, "program_chars": len(program),
                                             "stats_atoms": stats["atoms"], "stats_rules": stats["rules"],
                                             "model_limit": 0, "clingo_arguments": " ".join(arguments)})
                    record_metric("clingo", {"operation_category": "solving", "phase_context": "clause_generation",
                                             "seconds": solving, "program_size": 1, "models": stats["models"],
                                             "stats_choices": stats["choices"], "stats_conflicts": stats["conflicts"],
                                             "clingo_arguments": " ".join(arguments)})
        return ClauseSpace(index)
