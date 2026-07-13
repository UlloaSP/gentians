import time

import clingo

from .callbacks import WrapperStopIfWarn
from .coverage import Coverage
from .coverage_program import (
    build_coverage_static_program,
    clause_with_atom,
)
from .coverage_symbols import parse_coverage_symbol_masks, selected_symbol
from .stats import clingo_stat, ground_stats
from ..rule_generation.example import Example
from ..rule_generation.parser import clause_predicates
from ..timing import add, current_phase, instrumentation, metric_enabled, record_metric


class PregroundedCoverageSolver:
    """Ground rule universe once; evaluate candidates through activation strategy."""

    def __init__(
        self,
        lines: list[str],
        clingo_arguments: list[str],
        interpretation_pos: list[Example],
        interpretation_neg: list[Example],
        rule_space: tuple[str, ...],
        activation,
        max_program_clauses: int,
    ) -> None:
        self.activation = activation
        self.clingo_arguments = clingo_arguments
        self.positive_examples = len(interpretation_pos)
        self.negative_examples = len(interpretation_neg)
        self.coverage_static_program = build_coverage_static_program(
            lines, interpretation_pos, interpretation_neg
        )
        self.static_heads, self.static_dependencies, _ = clause_predicates(
            self.coverage_static_program
        )
        self.static_dependencies = self.static_dependencies - {
            ("neg_exs", 1),
            ("pos_exs", 1),
            ("cni", 1),
            ("cne", 1),
            ("cpi", 1),
            ("cpe", 1),
        }
        self.rule_ids = {rule: index for index, rule in enumerate(rule_space)}
        if len(self.rule_ids) != len(rule_space):
            raise ValueError("Pre-grounded rule space must not contain duplicates")

        activations = activation.declaration(max_program_clauses, len(rule_space))
        guarded = "\n".join(
            clause_with_atom(rule, f"selected({slot}), active({slot},{rule_id})")
            for slot in range(max_program_clauses)
            for rule_id, rule in enumerate(rule_space)
        )
        generated_program = "\n".join(
            part
            for part in (
                self.coverage_static_program,
                activations,
                "{selected(S)} :- active(S,R).\n#show selected/1.",
                guarded,
            )
            if part
        )
        wrapper = WrapperStopIfWarn()
        self.ctl = clingo.Control(
            clingo_arguments, logger=wrapper.wrapper_warn_undefined_callback
        )  # type: ignore
        self.ctl.add("base", [], generated_program)
        start = time.perf_counter()
        self.ctl.ground([("base", [])])
        seconds = time.perf_counter() - start
        phase = current_phase()
        add(f"{phase}.grounding", seconds)
        self.max_program_clauses = max_program_clauses
        self._record_grounding(
            seconds,
            len(lines) + len(rule_space) * max_program_clauses,
            len(generated_program),
        )

    def extract_subset_coverage(
        self, program: tuple[str, ...]
    ) -> dict[tuple[int, ...], Coverage] | None:
        return self._extract(program, subsets=True)

    def extract_fixed_coverage(self, program: tuple[str, ...]) -> Coverage:
        coverages = self._extract(program, subsets=False)
        return next(iter(coverages.values())) if coverages else Coverage([], [])

    def _extract(
        self, program: tuple[str, ...], *, subsets: bool
    ) -> dict[tuple[int, ...], Coverage] | None:
        try:
            candidate_ids = tuple(self.rule_ids[rule] for rule in program)
        except KeyError as error:
            raise ValueError(
                "Candidate contains rule outside pre-grounded rule space"
            ) from error
        if len(program) > self.max_program_clauses:
            raise ValueError("Candidate exceeds pre-grounded program slots")
        if not self._candidate_available(program):
            return None

        active_pairs = set(enumerate(candidate_ids))
        assumptions = self.activation.activate(
            self.ctl,
            active_pairs,
            self.max_program_clauses,
            self.rule_ids.values(),
        )
        if not subsets:
            assumptions.extend(
                (selected_symbol(slot), True) for slot in range(len(program))
            )
        coverages: dict[tuple[int, ...], Coverage] = {}
        start = time.perf_counter()
        models = 0
        try:
            with self.ctl.solve(
                yield_=True, assumptions=assumptions
            ) as handle:  # type: ignore
                for model in handle:  # type: ignore
                    models += 1
                    symbols = model.symbols(shown=True)
                    pos_mask, neg_mask = parse_coverage_symbol_masks(symbols)
                    selected = (
                        tuple(
                            sorted(
                                symbol.arguments[0].number
                                for symbol in symbols
                                if symbol.name == "selected"
                                and len(symbol.arguments) == 1
                            )
                        )
                        if subsets
                        else tuple(range(len(program)))
                    )
                    coverage = coverages.setdefault(selected, Coverage([], []))
                    coverage.extend_masks(pos_mask, neg_mask)
        finally:
            self.activation.deactivate(self.ctl, active_pairs)
        seconds = time.perf_counter() - start
        phase = current_phase()
        add(f"{phase}.solving", seconds)
        self._record_solving(seconds, models, len(program), len(coverages), subsets)
        return coverages

    def _candidate_available(self, program: tuple[str, ...]) -> bool:
        heads = set(self.static_heads)
        dependencies = set(self.static_dependencies)
        for rule in program:
            rule_heads, rule_dependencies, _ = clause_predicates(rule)
            heads.update(rule_heads)
            dependencies.update(rule_dependencies)
        return dependencies <= heads

    def _record_grounding(
        self, seconds: float, input_clauses: int, program_chars: int
    ) -> None:
        if not metric_enabled("clingo"):
            return
        with instrumentation():
            stats = ground_stats(self.ctl)
            record_metric(
                "clingo",
                {
                    "operation": f"preground_{self.activation.name}",
                    "operation_category": "grounding",
                    "phase_context": current_phase(),
                    "seconds": seconds,
                    "input_clauses": input_clauses,
                    "program_chars": program_chars,
                    "positive_examples": self.positive_examples,
                    "negative_examples": self.negative_examples,
                    "clingo_arguments": " ".join(self.clingo_arguments),
                    "stats_atoms": stats["atoms"],
                    "stats_rules": stats["rules"],
                },
            )

    def _record_solving(
        self,
        seconds: float,
        models: int,
        program_size: int,
        coverage_count: int,
        subsets: bool,
    ) -> None:
        if not metric_enabled("clingo"):
            return
        with instrumentation():
            stats = self.ctl.statistics
            operation = "subset" if subsets else "fixed"
            record_metric(
                "clingo",
                {
                    "operation": f"{operation}_presolve_{self.activation.name}",
                    "operation_category": "solving",
                    "phase_context": current_phase(),
                    "seconds": seconds,
                    "models": models,
                    "coverage_subsets": coverage_count,
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
