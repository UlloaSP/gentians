"""Bounded clause archive, enumeration lifetime and active clause sampling."""

import random
from collections.abc import Sequence
from contextlib import ExitStack

from ..arguments import Arguments
from ..clauses import Clause, ClauseSpace, incremental_clause_batches
from ..clauses.metrics import record_clause_space
from ..hypotheses import Genome, HypothesisGenerator
from ..language.ir.inductive_task import InductiveTask
from .search_budget import SearchBudget


class IncrementalClausePool:
    def __init__(
        self, task: InductiveTask, args: Arguments, batch_size: int, archive_size: int,
        rng: random.Random, budget: SearchBudget, supplied_space: ClauseSpace | None = None,
    ) -> None:
        self.task = task
        self.args = args
        self.batch_size = batch_size
        self.archive_size = archive_size
        self.rng = rng
        self.budget = budget
        self.supplied_space = supplied_space
        self.archive: dict[str, Clause] = {}
        self.exhausted = False
        self.overflow = False
        self.resources = ExitStack()

    def __enter__(self):
        self.batches = (
            iter([self.supplied_space]) if self.supplied_space is not None
            else self._open_batches()
        )
        return self

    def __exit__(self, *exc):
        return self.resources.__exit__(*exc)

    def _open_batches(self):
        return self.resources.enter_context(incremental_clause_batches(
            self.task, self.args, self.batch_size, self.rng,
        ))

    def draw(self, retained: Sequence[Clause] = ()) -> HypothesisGenerator | None:
        # Retain raw clauses: dependency providers may arrive in later batches.
        while True:
            self.budget.check()
            batch = next(self.batches, None)
            self.budget.check()
            if batch is None:
                self.exhausted = True
                if not self.overflow or self.supplied_space is not None or not retained:
                    return None
                self.resources.close()
                self.batches = self._open_batches()
                batch = next(self.batches, None)
                self.budget.check()
                if batch is None:
                    return None
                self.exhausted = False
            for entry in batch.entries:
                if entry.text not in self.archive:
                    if len(self.archive) < self.archive_size:
                        self.archive[entry.text] = entry
                    else:
                        self.overflow = True
            combined = ClauseSpace([*self.archive.values(), *retained, *batch.entries])
            limit = self.task.max_program_clauses or len(combined)
            hypotheses = HypothesisGenerator(self.task, combined, limit)
            if hypotheses.space and hypotheses.create(self.rng) is not None:
                record_clause_space(self.task, hypotheses.space)
                return hypotheses

    def activate(self, hypotheses: HypothesisGenerator, seeds: Sequence[Genome]) -> None:
        target = self.batch_size if self.overflow else hypotheses.clause_count
        activate_clauses(hypotheses, seeds, target, self.rng)


def activate_clauses(
    hypotheses: HypothesisGenerator, seeds: Sequence[Genome], target: int, rng: random.Random,
) -> Genome:
    hypotheses.set_available_clauses(hypotheses.all_clauses)
    if target >= hypotheses.clause_count:
        return hypotheses.all_clauses
    active = 0
    for genome in seeds:
        active |= genome
    target = min(target, hypotheses.clause_count)
    failures = 0
    while active.bit_count() < target and failures < 256:
        candidate = hypotheses.create(rng)
        if candidate is None or candidate & ~active == 0:
            failures += 1
            continue
        active |= candidate
        failures = 0
    if not active:
        candidate = hypotheses.create(rng)
        if candidate is None:
            raise RuntimeError("Could not construct an active clause batch")
        active = candidate
    hypotheses.set_available_clauses(active)
    return active
