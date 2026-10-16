"""Search budgets and the best completed evaluation at a stopping boundary."""

import math
import os
import time

from ..evaluation.result import EvaluationResult
from ..hypotheses import Genome, HypothesisGenerator
from ..timing import net_time
from .result import SearchResult


class SearchBudget:
    class Expired(Exception):
        """Stop at an operation boundary when a configured budget expires."""

    def __init__(self, seconds: object) -> None:
        started = net_time()
        if seconds is not None and (
            isinstance(seconds, bool) or not isinstance(seconds, (int, float))
            or not math.isfinite(seconds) or seconds <= 0
        ):
            raise ValueError("incremental.time_limit_seconds must be a finite positive number")
        self.deadline = None if seconds is None else started + seconds
        wall_deadline = os.environ.get("GENTIANS_RUN_DEADLINE")
        self.wall_deadline = None if wall_deadline is None else float(wall_deadline)
        self.best: SearchResult | None = None

    def check(self) -> None:
        if self.deadline is not None and net_time() >= self.deadline:
            raise self.Expired
        if self.wall_deadline is not None and time.monotonic() >= self.wall_deadline:
            raise self.Expired

    def accept(
        self, hypotheses: HypothesisGenerator, genome: Genome, result: EvaluationResult,
    ) -> None:
        # A wall timeout finishes the current evaluation before returning its best.
        # Keep the incremental net-budget rule, which rejects late evaluations.
        if self.deadline is not None and net_time() >= self.deadline:
            raise self.Expired
        if (self.deadline is not None or self.wall_deadline is not None) and (
            self.best is None or result.score > self.best.score
        ):
            self.best = SearchResult(hypotheses.render(genome), result.score, result.is_solution)
        self.check()

    def result(self) -> SearchResult:
        if self.best is None:
            if self.wall_deadline is not None and time.monotonic() >= self.wall_deadline:
                raise self.Expired from None
            raise RuntimeError("Time budget expired before any candidate was evaluated") from None
        return self.best
