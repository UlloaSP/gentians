import time
from dataclasses import dataclass, field

from .types import Behavior, Genome


@dataclass(slots=True)
class Individual:
    program: Genome
    score: float
    is_best: bool  # does this cover everything positive and no negative?
    behavior: Behavior = (0, 0)
    generated_timestamp: float = field(default_factory=time.time)
