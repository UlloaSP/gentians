import sys

import clingo

from ..clingo_stats import clingo_stat, ground_stats
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
from .coverage import Coverage
from .compiler import compile_coverage_program


class CoverageSolver:
    """Create, ground, and solve one Clingo control per candidate."""

    def __init__(
        self,
        background: AspProgram,
        clingo_arguments: list[str],
        positive_examples: list[Example],
        negative_examples: list[Example],
    ) -> None:
        self.background = background
        self.clingo_arguments = clingo_arguments
        self.positive_examples = len(positive_examples)
        self.negative_examples = len(negative_examples)
        self.coverage_program = compile_coverage_program(
            positive_examples, negative_examples
        )

    def extract_coverage(self, program: AspProgram) -> Coverage:
        ctl, grounding_seconds, phase = self._ground(program)
        solving_seconds, coverage = self._solve(ctl)
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
        ctl = clingo.Control(self.clingo_arguments, logger=_coverage_logger)
        add_program(ctl, self.coverage_program)
        add_program(ctl, self.background)
        add_program(ctl, program)
        start = net_time()
        ctl.ground([("base", [])])
        seconds = net_time() - start
        phase = current_phase()
        add(f"{phase}.grounding", seconds)
        return ctl, seconds, phase

    @staticmethod
    def _solve(ctl) -> tuple[float, Coverage]:
        seconds = 0.0
        pos_mask = 0
        neg_mask = 0
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
                positive, negative = _coverage_masks(model.symbols(shown=True))
                pos_mask |= positive
                neg_mask |= negative
            start = net_time()
        seconds += net_time() - start
        add(f"{current_phase()}.solving", seconds)
        return seconds, Coverage(pos_mask, neg_mask)

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
                        len(str(statement)) for statement in self.coverage_program
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


def _coverage_masks(symbols) -> tuple[int, int]:
    pos_mask = 0
    neg_mask = 0
    for symbol in symbols:
        if len(symbol.arguments) != 1:
            continue
        value = symbol.arguments[0].number
        if symbol.name == "extended_p":
            pos_mask |= 1 << value
        elif symbol.name == "extended_n":
            neg_mask |= 1 << value
    return pos_mask, neg_mask


def _coverage_logger(code, message):
    with instrumentation():
        if code != clingo.MessageCode.AtomUndefined:
            print(message, file=sys.stderr, end="" if message.endswith("\n") else "\n")
