"""Bounded clause archive, enumeration lifetime and active clause sampling."""

import random
from collections.abc import Sequence
from contextlib import ExitStack

from ..arguments import Arguments
from ..clauses import Clause, ClauseSpace, incremental_clause_batches
from ..clauses.metrics import record_clause_space
from ..hypotheses import Genome, HypothesisGenerator
from ..language.ir.inductive_task import InductiveTask
from ..timing import net_time
from .budget import SearchBudget


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
        # Net seconds spent activating clause batches, read by epoch metrics.
        self.build_seconds = 0.0
        # Clause texts of the batches behind the last drawn space, until activation.
        self.arrived: tuple[str, ...] = ()

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
        arrived: list[str] = []
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
            arrived.extend(entry.text for entry in batch.entries)
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
                self.arrived = tuple(arrived)
                return hypotheses

    def activate(self, hypotheses: HypothesisGenerator, seeds: Sequence[Genome]) -> None:
        started = net_time()
        if self.exhausted:
            # Nothing else arrives: search continues on every archived clause.
            self.arrived = ()
            hypotheses.set_available_clauses(hypotheses.all_clauses)
            self.build_seconds += net_time() - started
            return
        arrived = 0
        for text in self.arrived:
            clause_id = hypotheses.clause_ids.get(text)
            if clause_id is not None:
                arrived |= 1 << clause_id
        self.arrived = ()
        activate_clauses(hypotheses, seeds, arrived, self.rng)
        self.build_seconds += net_time() - started


def activate_clauses(
    hypotheses: HypothesisGenerator, seeds: Sequence[Genome], arrived: Genome, rng: random.Random,
) -> Genome:
    """Activate the seeds and the closed programs of the arriving clauses.

    Each arriving clause joins with the providers that close it, which may
    come from the whole space. Without arrivals the active clauses stay.
    """
    active = 0
    for genome in seeds:
        active |= genome
    if not arrived:
        active |= hypotheses.available_clauses
    else:
        hypotheses.set_available_clauses(hypotheses.all_clauses)
        for clause_id in hypotheses._ids(arrived):
            closed = hypotheses.close(1 << clause_id, rng)
            if closed is not None:
                active |= closed
    if not active:
        raise RuntimeError("Could not construct an active clause batch")
    hypotheses.set_available_clauses(active)
    return active
