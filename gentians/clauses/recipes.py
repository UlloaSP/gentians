"""Native rule recipes, with bounded caches only for requested syntax."""

from functools import lru_cache
from array import array

from .canonicalization.canonical_clause import CanonicalArithmeticClause
from .clause_mode import ClauseMode
from .native_syntax import RuleBuilder, rule_text
from .reified_clause import instantiate_literal, instantiate_head
from .packed_recipe import PackedRecipe


class RuleRecipes:
    def __init__(self, modes: dict[int, ClauseMode]) -> None:
        self.modes = modes
        self.builder = RuleBuilder()
        self.pool = []
        self.pool_ids = {}

        @lru_cache(maxsize=8192)
        def literal(mode_id, variables):
            return instantiate_literal(modes[mode_id].literal, variables)

        # Clingo renders every element once. A rule repeats elements far more
        # often than it introduces new ones, so only the rule frame is per clause.
        @lru_cache(maxsize=8192)
        def literal_text(mode_id, variables):
            return self.builder.render(literal(mode_id, variables))

        @lru_cache(maxsize=8192)
        def head_text(head):
            return self.builder.render(instantiate_head(head, modes))

        @lru_cache(maxsize=8192)
        def system_texts(system):
            return tuple(self.builder.render(node) for node in system.instantiate())

        self.literal = literal
        self.literal_text = literal_text
        self.head_text = head_text
        self.system_texts = system_texts
        self.instantiate = lru_cache(maxsize=8192)(
            lambda recipe: recipe.instantiate(self.modes, builder=self.builder, literals=self.literal)
        )

    def render(self, recipe: CanonicalArithmeticClause) -> str:
        literal_text = self.literal_text
        body = [literal_text(literal.mode_id, literal.variables) for literal in recipe.body]
        for system in recipe.systems:
            body.extend(self.system_texts(system))
        if not recipe.head and not body:
            raise ValueError("a learned clause cannot have an empty head and body")
        return rule_text(self.head_text(recipe.head), body)

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
