import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .program_generators import ProgramGenerator


@dataclass(frozen=True, slots=True)
class EvolutionContext:
    generator: ProgramGenerator
    rng: random.Random
