from __future__ import annotations

from dataclasses import dataclass
import random
from typing import TYPE_CHECKING

from ..rule_generation.rule_space import RuleSpace

if TYPE_CHECKING:
    from .program_generators import ProgramGenerator


@dataclass(frozen=True, slots=True)
class EvolutionContext:
    space: RuleSpace
    generator: ProgramGenerator
    max_program_clauses: int
    rng: random.Random
