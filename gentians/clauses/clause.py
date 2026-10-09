from dataclasses import dataclass, field

from clingo import ast

from ..language.asp import Predicate
from .canonicalization.canonical_clause import CanonicalArithmeticClause
from .metadata import ClauseMetadata
from .recipes import RuleRecipes
from .packed_recipe import PackedRecipe


@dataclass(frozen=True, slots=True)
class Clause:
    text: str
    syntax: ast.AST | CanonicalArithmeticClause | PackedRecipe = field(compare=False, repr=False)
    metadata: ClauseMetadata
    recipes: RuleRecipes | None = field(default=None, compare=False, repr=False)

    @property
    def statement(self) -> ast.AST:
        if isinstance(self.syntax, ast.AST):
            return self.syntax
        if self.recipes is None:
            raise ValueError("a generated clause needs its native mode recipes")
        return self.recipes.statement(self.syntax)

    @property
    def heads(self) -> frozenset[Predicate]:
        return self.metadata.index.members(self.metadata.head_mask)

    @property
    def deps(self) -> frozenset[Predicate]:
        return self.metadata.index.members(self.metadata.dep_mask)

    @property
    def body_literals(self) -> int:
        return self.metadata.body_literals
