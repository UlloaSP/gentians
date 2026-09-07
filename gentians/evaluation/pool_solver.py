"""Coverage solver for a clause pool frozen between search epochs."""

from collections.abc import Sequence

import clingo
from clingo import ast

from ..clingo_stats import clingo_stat, ground_stats
from ..clauses.clause_space import ClauseSpace
from ..language.asp import AspProgram, add_program
from ..language.ir.inductive_task import InductiveTask
from ..timing import (
    add,
    current_phase,
    instrumentation,
    metric_enabled,
    net_time,
    record_metric,
)
from .compiler import compile_coverage_program
from .coverage import Coverage
from .solver import _coverage_logger, _coverage_masks


ACTIVE_CLAUSE_PREDICATE = "gentians_internal_epoch_clause"


class EpochPoolCoverageSolver:
    """Ground a frozen clause pool once, then evaluate its subsets."""

    def __init__(
        self,
        task: InductiveTask,
        clingo_arguments: Sequence[str],
        pool: ClauseSpace,
        *,
        coverage_program: AspProgram | None = None,
    ) -> None:
        self.pool = pool
        self._task = task
        self._clingo_arguments = list(clingo_arguments)
        self._coverage_program = (
            compile_coverage_program(task.positive_examples, task.negative_examples)
            if coverage_program is None
            else coverage_program
        )
        self._indices = {
            clause.statement: index for index, clause in enumerate(pool.entries)
        }
        self._selected: frozenset[int] = frozenset()
        self._symbols = tuple(_active_clause(index) for index in range(len(pool)))
        self._guarded_pool_program = self._guarded_pool()
        self.control = clingo.Control(self._clingo_arguments, logger=_coverage_logger)
        add_program(self.control, self._coverage_program)
        add_program(self.control, task.background)
        add_program(self.control, self._guarded_pool_program)
        start = net_time()
        self.control.ground([("base", [])])
        self.grounding_seconds = net_time() - start
        phase = current_phase()
        add(f"{phase}.grounding", self.grounding_seconds)
        self._record_grounding(phase)

    def extract_coverage(self, program: AspProgram) -> Coverage:
        try:
            selected = frozenset(self._indices[statement] for statement in program)
        except KeyError as error:
            raise ValueError(f"clauses outside frozen pool: {error.args[0]}") from None

        for index in self._selected ^ selected:
            self.control.assign_external(self._symbols[index], index in selected)
        self._selected = selected

        seconds = 0.0
        pos_mask = 0
        neg_mask = 0
        start = net_time()
        with self.control.solve(yield_=True) as handle:
            seconds += net_time() - start
            iterator = iter(handle)
            while True:
                start = net_time()
                try:
                    model = next(iterator)
                except StopIteration:
                    seconds += net_time() - start
                    break
                seconds += net_time() - start
                positive, negative = _coverage_masks(model.symbols(shown=True))
                pos_mask |= positive
                neg_mask |= negative
            start = net_time()
        seconds += net_time() - start
        add(f"{current_phase()}.solving", seconds)
        coverage = Coverage(pos_mask, neg_mask)
        self._record_solving(program, coverage, seconds)
        return coverage

    def _guarded_pool(self) -> AspProgram:
        statements: list[ast.AST] = []
        for clause, symbol in zip(self.pool.entries, self._symbols):
            location = clause.statement.location
            atom = ast.SymbolicAtom(ast.SymbolicTerm(location, symbol))
            statements.append(
                ast.External(
                    location, atom, [], ast.SymbolicTerm(location, clingo.Function("false"))
                )
            )
            guard = ast.Literal(location, ast.Sign.NoSign, atom)
            statements.append(
                clause.statement.update(body=[*clause.statement.body, guard])
            )
        return tuple(statements)

    def _record_grounding(self, phase: str) -> None:
        if not metric_enabled("clingo"):
            return
        with instrumentation():
            grounded = ground_stats(self.control.statistics)
            record_metric(
                "clingo",
                {
                    **self._metric_fields(len(self.pool)),
                    "phase_context": phase,
                    "operation_category": "grounding",
                    "seconds": self.grounding_seconds,
                    "input_clauses": len(self._task.background) + len(self.pool),
                    "program_chars": sum(
                        len(str(statement))
                        for statement in (
                            *self._coverage_program,
                            *self._task.background,
                            *self._guarded_pool_program,
                        )
                    ),
                    "stats_atoms": grounded["atoms"],
                    "stats_rules": grounded["rules"],
                },
            )

    def _record_solving(
        self,
        program: AspProgram,
        coverage: Coverage,
        seconds: float,
    ) -> None:
        if not metric_enabled("clingo"):
            return
        with instrumentation():
            stats = self.control.statistics
            record_metric(
                "clingo",
                {
                    **self._metric_fields(len(program)),
                    "phase_context": current_phase(),
                    "operation_category": "solving",
                    "seconds": seconds,
                    "models": clingo_stat(stats, "summary", "models", "enumerated"),
                    "covered_positive": coverage.pos_mask.bit_count(),
                    "covered_negative": coverage.neg_mask.bit_count(),
                    "stats_choices": clingo_stat(
                        stats, "solving", "solvers", "choices"
                    ),
                    "stats_conflicts": clingo_stat(
                        stats, "solving", "solvers", "conflicts"
                    ),
                },
            )

    def _metric_fields(self, program_size: int) -> dict[str, object]:
        return {
            "program_size": program_size,
            "clingo_arguments": " ".join(self._clingo_arguments),
            "positive_examples": len(self._task.positive_examples),
            "negative_examples": len(self._task.negative_examples),
        }


def _active_clause(index: int) -> clingo.Symbol:
    return clingo.Function(ACTIVE_CLAUSE_PREDICATE, [clingo.Number(index)])
