import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..hypotheses import HypothesisGenerator


@dataclass(frozen=True, slots=True)
class EvolutionContext:
    hypotheses: HypothesisGenerator
    rng: random.Random
