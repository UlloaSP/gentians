from dataclasses import dataclass

from ..hypotheses import Genome
from .types import Behavior


@dataclass(slots=True)
class Individual:
    genome: Genome
    score: float
    is_solution: bool
    behavior: Behavior = (0, 0)
    birth_order: int = 0
