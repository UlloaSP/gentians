from dataclasses import dataclass

from ..evaluation.result import Behavior
from ..hypotheses import Genome


@dataclass(frozen=True, slots=True)
class Individual:
    genome: Genome
    score: float
    is_solution: bool
    behavior: Behavior = (0, 0)
    birth_order: int = 0
