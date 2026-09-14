"""Net-time budget and the best complete evaluation obtained within it."""

import math

from ..evaluation.result import EvaluationResult
from ..hypotheses import Genome, HypothesisGenerator
from ..timing import net_time
from .result import SearchResult


class SearchBudget:
    class Expired(Exception):
        """Stop at an operation boundary without accepting a late evaluation."""

    def __init__(self, seconds: object) -> None:
        started = net_time()
        if seconds is not None and (
            isinstance(seconds, bool) or not isinstance(seconds, (int, float))
            or not math.isfinite(seconds) or seconds <= 0
        ):
            raise ValueError("incremental.time_limit_seconds must be a finite positive number")
        self.deadline = None if seconds is None else started + seconds
        self.best: SearchResult | None = None

    def check(self) -> None:
        if self.deadline is not None and net_time() >= self.deadline:
            raise self.Expired

    def accept(
        self, hypotheses: HypothesisGenerator, genome: Genome, result: EvaluationResult,
    ) -> None:
        self.check()
        if self.deadline is not None and (self.best is None or result.score > self.best.score):
            self.best = SearchResult(hypotheses.render(genome), result.score, result.is_solution)

    def result(self) -> SearchResult:
        if self.best is None:
            raise RuntimeError("Time budget expired before any candidate was evaluated") from None
        return self.best
