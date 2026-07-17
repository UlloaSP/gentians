from dataclasses import dataclass
import random

from .program_generators import ProgramGenerator
from ..rule_generation.rule_space import RuleSpace


@dataclass(frozen=True, slots=True)
class EvolutionContext:
    space: RuleSpace
    generator: ProgramGenerator
    max_program_clauses: int
    rng: random.Random
