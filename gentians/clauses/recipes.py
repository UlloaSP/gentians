"""Native rule recipes, with a bounded cache only for requested ASTs."""

from functools import lru_cache
from array import array

from clingo._internal import _ffi

from .canonicalization.canonical_clause import CanonicalArithmeticClause
from .clause_mode import ClauseMode
from .native_syntax import RuleBuilder
from .reified_clause import instantiate_literal, instantiate_head
from .packed_recipe import PackedRecipe


class RuleRecipes:
    def __init__(self, modes: dict[int, ClauseMode]) -> None:
        self.modes = modes
        self.builder = RuleBuilder()
        self.pool = []
        self.pool_ids = {}

        @lru_cache(maxsize=8192)
        def literal_pair(mode_id, variables):
            node = instantiate_literal(modes[mode_id].literal, variables)
            return node, int(_ffi.cast("uintptr_t", node._rep))

        @lru_cache(maxsize=8192)
        def head_pair(head):
            node = instantiate_head(head, modes)
            return node, int(_ffi.cast("uintptr_t", node._rep))

        @lru_cache(maxsize=8192)
        def system_pairs(system):
            return tuple((node, int(_ffi.cast("uintptr_t", node._rep))) for node in system.instantiate())

        self.literal_pair = literal_pair
        self.head_pair = head_pair
        self.system_pairs = system_pairs
        self.instantiate = lru_cache(maxsize=8192)(
            lambda recipe: recipe.instantiate(self.modes, builder=self.builder, literals=self.literal)
        )

    def literal(self, mode_id, variables):
        return self.literal_pair(mode_id, variables)[0]

    def parts(self, recipe):
        head = self.head_pair(recipe.head)
        body = [self.literal_pair(literal.mode_id, literal.variables) for literal in recipe.body]
        for system in recipe.systems:
            body.extend(self.system_pairs(system))
        # Owners accompany every borrowed address, even when a long rule evicts
        # an earlier literal from the bounded cache while preparing this rule.
        return (head[1], tuple(pair[1] for pair in body)), (head[0], *(pair[0] for pair in body))

    def render_many(self, recipes):
        if self.builder.renderer is None:
            return tuple(self.builder.render(self.instantiate(recipe)) for recipe in recipes)
        rows = tuple(self.parts(recipe) for recipe in recipes)
        return self.builder.render_parts(tuple(row[0] for row in rows))

    def render(self, recipe):
        return self.render_many((recipe,))[0]

    def statement(self, recipe: CanonicalArithmeticClause | PackedRecipe):
        if isinstance(recipe, PackedRecipe):
            indexes = array("I")
            indexes.frombytes(recipe.codes)
            literals = tuple(self.pool[index] for index in indexes)
            recipe = CanonicalArithmeticClause(literals[:recipe.head_length], literals[recipe.head_length:], recipe.systems)
        return self.instantiate(recipe)

    def pack(self, recipe):
        if not isinstance(recipe, CanonicalArithmeticClause):
            return recipe
        codes = array("I", (self.pool_index(literal) for literal in (*recipe.head, *recipe.body)))
        return PackedRecipe(codes.tobytes(), len(recipe.head), recipe.systems)

    def pool_index(self, literal):
        # Syntax uses mode/bindings and tuple order. The original selection slot
        # matters during legality/canonicalization, never during materialization.
        index = self.pool_ids.get(literal.key)
        if index is None:
            index = len(self.pool)
            self.pool_ids[literal.key] = index
            self.pool.append(literal)
        return index
