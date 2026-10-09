"""Owned literal-pool indexes; native syntax is still built by RuleRecipes."""

from dataclasses import dataclass

from .canonicalization.arithmetic_system import ArithmeticSystem


@dataclass(frozen=True, slots=True)
class PackedRecipe:
    codes: bytes
    head_length: int
    systems: tuple[ArithmeticSystem, ...]
