from dataclasses import dataclass
import random

from .closures.contract import Closure
from ..rule_generation.rule_space import RuleSpace


@dataclass(frozen=True, slots=True)
class EvolutionContext:
    space: RuleSpace
    policy: Closure
    max_program_clauses: int
    rng: random.Random
