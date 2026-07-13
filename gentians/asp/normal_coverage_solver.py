import time

import clingo

from .callbacks import WrapperStopIfWarn
from .coverage import Coverage
from .coverage_program import (
    build_coverage_static_program,
    build_subset_coverage_program,
)
from .coverage_symbols import parse_coverage_symbol_masks, parse_selected_rule_tuple
from .stats import clingo_stat, ground_stats
from ..rule_generation.example import Example
from ..timing import add, current_phase, instrumentation, metric_enabled, record_metric


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
        ctl, undefined, seconds = self._ground(generated_program, "grounding", program)
        if undefined:
            return Coverage([], [])

        coverage = Coverage([], [])
        start = time.perf_counter()
        models = 0
        collect_metrics = metric_enabled("clingo")
        with ctl.solve(yield_=True) as handle:  # type: ignore
            for model in handle:  # type: ignore
                if collect_metrics:
                    models += 1
                coverage.extend_masks(
                    *parse_coverage_symbol_masks(model.symbols(shown=True))
                )
        seconds = time.perf_counter() - start
        phase = current_phase()
        add(f"{phase}.solving", seconds)
        if collect_metrics:
            self._record_solving(ctl, seconds, models, coverage, len(program), "solving")
        return coverage

    def extract_subset_coverage(
        self, program: tuple[str, ...]
    ) -> dict[tuple[int, ...], Coverage] | None:
        generated_program = build_subset_coverage_program(
            self.coverage_static_program, program
        )
        ctl, undefined, _ = self._ground(
            generated_program, "subset_coverage_grounding", program
        )
        if undefined:
            return None

        coverages: dict[tuple[int, ...], Coverage] = {}
        start = time.perf_counter()
        models = 0
        collect_metrics = metric_enabled("clingo")
        with ctl.solve(yield_=True) as handle:  # type: ignore
            for model in handle:  # type: ignore
                if collect_metrics:
                    models += 1
                symbols = model.symbols(shown=True)
                coverage = coverages.setdefault(
                    parse_selected_rule_tuple(symbols), Coverage([], [])
                )
                coverage.extend_masks(*parse_coverage_symbol_masks(symbols))
        seconds = time.perf_counter() - start
        phase = current_phase()
        add(f"{phase}.solving", seconds)
        if collect_metrics:
            merged = Coverage([], [])
            for coverage in coverages.values():
                merged.extend_masks(coverage.pos_mask, coverage.neg_mask)
            self._record_solving(
                ctl,
                seconds,
                models,
                merged,
                len(program),
                "subset_coverage_solving",
            )
        return coverages

    def _ground(self, generated_program: str, operation: str, program):
        wrapper = WrapperStopIfWarn()
        ctl = clingo.Control(
            self.clingo_arguments, logger=wrapper.wrapper_warn_undefined_callback
        )  # type: ignore
        ctl.add("base", [], generated_program)
        start = time.perf_counter()
        ctl.ground([("base", [])])
        seconds = time.perf_counter() - start
        phase = current_phase()
        add(f"{phase}.grounding", seconds)
        if metric_enabled("clingo"):
            with instrumentation():
                stats = ground_stats(ctl)
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
                        "stats_atoms": stats["atoms"],
                        "stats_rules": stats["rules"],
                    },
                )
        return ctl, wrapper.atom_undefined, seconds

    def _record_solving(
        self,
        ctl,
        seconds: float,
        models: int,
        coverage: Coverage,
        program_size: int,
        operation: str,
    ) -> None:
        with instrumentation():
            stats = ctl.statistics
            record_metric(
                "clingo",
                {
                    "operation": operation,
                    "operation_category": "solving",
                    "phase_context": current_phase(),
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
