import random
from dataclasses import dataclass
from typing import TYPE_CHECKING
from collections.abc import Callable, Mapping

if TYPE_CHECKING:
    from ..hypotheses import HypothesisGenerator
    from ..evaluation.result import EvaluationResult
    from ..hypotheses import Genome, GenomeTable


@dataclass(frozen=True, slots=True)
class EvolutionContext:
    hypotheses: HypothesisGenerator
    rng: random.Random
    evaluate: Callable[[Genome], EvaluationResult] | None = None
    # Operators only call `get`; search passes a GenomeTable, unit tests a dict.
    results: GenomeTable[EvaluationResult] | Mapping[Genome, EvaluationResult] | None = None
