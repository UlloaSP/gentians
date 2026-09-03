import clingo

from ..language.asp import AspProgram, add_program
from ..language.ir.example import Example
from ..timing import (
    add,
    current_phase,
    instrumentation,
    metric_enabled,
    net_time,
    record_metric,
)
from .callbacks import coverage_logger
from .coverage import Coverage
from .coverage_program import build_coverage_static_program
from .coverage_symbols import parse_coverage_symbol_masks
from .stats import clingo_stat, ground_stats


class NormalCoverageSolver:
    """Create, ground, and solve one Clingo control per fitness evaluation."""

    def __init__(
        self,
        background: AspProgram,
        clingo_arguments: list[str],
        interpretation_pos: list[Example],
        interpretation_neg: list[Example],
    ) -> None:
        self.background = background
        self.clingo_arguments = clingo_arguments
        self.positive_examples = len(interpretation_pos)
        self.negative_examples = len(interpretation_neg)
        self.coverage_static_program = build_coverage_static_program(
            interpretation_pos, interpretation_neg
        )

    def extract_fixed_coverage(self, program: AspProgram) -> Coverage:
        ctl, grounding_seconds, phase = self._ground(program)
        coverage = Coverage()
        solving_seconds = self._solve(
            ctl,
            lambda symbols: coverage.extend_masks(
                *parse_coverage_symbol_masks(symbols)
            ),
        )
        self._record(
            ctl,
            program,
            coverage,
            grounding_seconds,
            solving_seconds,
            phase,
        )
        return coverage

    def _ground(self, program: AspProgram):
        ctl = clingo.Control(self.clingo_arguments, logger=coverage_logger)
        add_program(ctl, self.coverage_static_program)
        add_program(ctl, self.background)
        add_program(ctl, program)
        start = net_time()
        ctl.ground([("base", [])])
        seconds = net_time() - start
        phase = current_phase()
        add(f"{phase}.grounding", seconds)
        return ctl, seconds, phase

    @staticmethod
    def _solve(ctl, collect) -> float:
        seconds = 0.0
        start = net_time()
        with ctl.solve(yield_=True) as handle:
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
                collect(model.symbols(shown=True))
            start = net_time()
        seconds += net_time() - start
        add(f"{current_phase()}.solving", seconds)
        return seconds

    def _record(
        self,
        ctl,
        program: AspProgram,
        coverage: Coverage,
        grounding_seconds: float,
        solving_seconds: float,
        phase: str,
    ) -> None:
        if not metric_enabled("clingo"):
            return
        with instrumentation():
            stats = ctl.statistics
            grounded = ground_stats(stats)
            common = {
                "phase_context": phase,
                "program_size": len(program),
                "clingo_arguments": " ".join(self.clingo_arguments),
            }
            record_metric(
                "clingo",
                {
                    **common,
                    "operation_category": "grounding",
                    "seconds": grounding_seconds,
                    "input_clauses": len(self.background) + len(program),
                    "program_chars": sum(
                        len(str(statement))
                        for statement in self.coverage_static_program
                    )
                    + sum(len(str(statement)) for statement in self.background)
                    + sum(len(str(statement)) for statement in program),
                    "positive_examples": self.positive_examples,
                    "negative_examples": self.negative_examples,
                    "stats_atoms": grounded["atoms"],
                    "stats_rules": grounded["rules"],
                },
            )
            record_metric(
                "clingo",
                {
                    **common,
                    "operation_category": "solving",
                    "seconds": solving_seconds,
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
