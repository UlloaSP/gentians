import random
from dataclasses import dataclass
from typing import TYPE_CHECKING
from collections.abc import Callable, Mapping

if TYPE_CHECKING:
    from ..hypotheses import HypothesisGenerator
    from ..evaluation.result import EvaluationResult
    from ..hypotheses import Genome


@dataclass(frozen=True, slots=True)
class EvolutionContext:
    hypotheses: HypothesisGenerator
    rng: random.Random
    evaluate: Callable[[Genome], EvaluationResult] | None = None
    results: Mapping[Genome, EvaluationResult] | None = None
