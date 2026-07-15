import clingo

from .callbacks import coverage_logger
from .coverage import Coverage
from .coverage_program import (
    build_coverage_static_program,
    build_subset_coverage_program,
)
from .coverage_symbols import parse_coverage_symbol_masks, parse_selected_rule_tuple
from .stats import clingo_stat, ground_stats
from ..rule_generation.example import Example
from ..timing import (
    add,
    current_phase,
    instrumentation,
    metric_enabled,
    net_time,
    record_metric,
)


class NormalCoverageSolver:
    def __init__(
        self,
        lines: list[str],
        clingo_arguments: list[str],
        interpretation_pos: list[Example],
        interpretation_neg: list[Example],
    ) -> None:
        self.lines = lines
        self.clingo_arguments = clingo_arguments
        self.positive_examples = len(interpretation_pos)
        self.negative_examples = len(interpretation_neg)
        self.coverage_static_program = build_coverage_static_program(
            lines, interpretation_pos, interpretation_neg
        )

    def extract_fixed_coverage(self, program: tuple[str, ...]) -> Coverage:
        generated_program = self.coverage_static_program + "\n" + "\n".join(program)
        ctl, grounding_seconds, phase = self._ground(generated_program)

        coverage = Coverage([], [])
        seconds = 0.0
        collect_metrics = metric_enabled("clingo")
        start = net_time()
        with ctl.solve(yield_=True) as handle:  # type: ignore
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
                coverage.extend_masks(
                    *parse_coverage_symbol_masks(model.symbols(shown=True))
                )
            start = net_time()
        seconds += net_time() - start
        phase = current_phase()
        add(f"{phase}.solving", seconds)
        if collect_metrics:
            with instrumentation():
                stats = ctl.statistics
                self._record_grounding(
                    stats,
                    grounding_seconds,
                    generated_program,
                    program,
                    "grounding",
                    phase,
                )
                self._record_solving(
                    stats, seconds, coverage, len(program), "solving", phase
                )
        return coverage

    def extract_subset_coverage(
        self, program: tuple[str, ...]
    ) -> dict[tuple[int, ...], Coverage] | None:
        generated_program = build_subset_coverage_program(
            self.coverage_static_program, program
        )
        ctl, grounding_seconds, phase = self._ground(generated_program)

        coverages: dict[tuple[int, ...], Coverage] = {}
        seconds = 0.0
        collect_metrics = metric_enabled("clingo")
        start = net_time()
        with ctl.solve(yield_=True) as handle:  # type: ignore
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
                symbols = model.symbols(shown=True)
                coverage = coverages.setdefault(
                    parse_selected_rule_tuple(symbols), Coverage([], [])
                )
                coverage.extend_masks(*parse_coverage_symbol_masks(symbols))
            start = net_time()
        seconds += net_time() - start
        phase = current_phase()
        add(f"{phase}.solving", seconds)
        if collect_metrics:
            with instrumentation():
                stats = ctl.statistics
                merged = Coverage([], [])
                for coverage in coverages.values():
                    merged.extend_masks(coverage.pos_mask, coverage.neg_mask)
                self._record_grounding(
                    stats,
                    grounding_seconds,
                    generated_program,
                    program,
                    "subset_coverage_grounding",
                    phase,
                )
                self._record_solving(
                    stats,
                    seconds,
                    merged,
                    len(program),
                    "subset_coverage_solving",
                    phase,
                )
        return coverages

    def _ground(self, generated_program: str):
        ctl = clingo.Control(self.clingo_arguments, logger=coverage_logger)  # type: ignore
        ctl.add("base", [], generated_program)
        start = net_time()
        ctl.ground([("base", [])])
        seconds = net_time() - start
        phase = current_phase()
        add(f"{phase}.grounding", seconds)
        return ctl, seconds, phase

    def _record_grounding(
        self,
        stats,
        seconds: float,
        generated_program: str,
        program: tuple[str, ...],
        operation: str,
        phase: str,
    ) -> None:
        with instrumentation():
            grounded = ground_stats(stats)
            record_metric(
                "clingo",
                {
                    "operation": operation,
                    "operation_category": "grounding",
                    "phase_context": phase,
                    "seconds": seconds,
                    "input_clauses": len(self.lines) + len(program),
                    "program_chars": len(generated_program),
                    "positive_examples": self.positive_examples,
                    "negative_examples": self.negative_examples,
                    "clingo_arguments": " ".join(self.clingo_arguments),
                    "stats_atoms": grounded["atoms"],
                    "stats_rules": grounded["rules"],
                },
            )

    def _record_solving(
        self,
        stats,
        seconds: float,
        coverage: Coverage,
        program_size: int,
        operation: str,
        phase: str,
    ) -> None:
        with instrumentation():
            models = clingo_stat(stats, "summary", "models", "enumerated")
            record_metric(
                "clingo",
                {
                    "operation": operation,
                    "operation_category": "solving",
                    "phase_context": phase,
                    "seconds": seconds,
                    "models": models,
                    "covered_positive": coverage.pos_mask.bit_count(),
                    "covered_negative": coverage.neg_mask.bit_count(),
                    "program_size": program_size,
                    "clingo_arguments": " ".join(self.clingo_arguments),
                    "stats_models_enumerated": clingo_stat(
                        stats, "summary", "models", "enumerated"
                    ),
                    "stats_choices": clingo_stat(
                        stats, "solving", "solvers", "choices"
                    ),
                    "stats_conflicts": clingo_stat(
                        stats, "solving", "solvers", "conflicts"
                    ),
                },
            )
