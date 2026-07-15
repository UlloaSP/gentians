import clingo

from .callbacks import coverage_logger
from .coverage import Coverage
from .coverage_program import (
    build_coverage_static_program,
    clause_with_atom,
)
from .coverage_symbols import (
    ACTIVE_PREDICATE,
    SELECTED_PREDICATE,
    parse_coverage_symbol_masks,
    selected_symbol,
)
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
        self.rule_ids = {rule: index for index, rule in enumerate(rule_space)}
        if len(self.rule_ids) != len(rule_space):
            raise ValueError("Pre-grounded rule space must not contain duplicates")

        activations = activation.declaration(len(rule_space))
        guarded = "\n".join(
            clause_with_atom(rule, f"{SELECTED_PREDICATE}({rule_id})")
            for rule_id, rule in enumerate(rule_space)
        )
        generated_program = "\n".join(
            part
            for part in (
                self.coverage_static_program,
                activations,
                f"{{{SELECTED_PREDICATE}(R)}} :- {ACTIVE_PREDICATE}(R).\n"
                f"#show {SELECTED_PREDICATE}/1.",
                guarded,
            )
            if part
        )
        self.ctl = clingo.Control(clingo_arguments, logger=coverage_logger)  # type: ignore
        self.ctl.add("base", [], generated_program)
        start = net_time()
        self.ctl.ground([("base", [])])
        seconds = net_time() - start
        phase = current_phase()
        add(f"{phase}.grounding", seconds)
        self.max_program_clauses = max_program_clauses
        self._pending_grounding = (
            seconds,
            len(lines) + len(rule_space),
            len(generated_program),
            phase,
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
            raise ValueError("Candidate exceeds max_program_clauses")
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("Pre-grounded candidate must not contain duplicate rules")
        active_rule_ids = set(candidate_ids)
        assumptions = self.activation.activate(
            self.ctl,
            active_rule_ids,
            self.rule_ids.values(),
        )
        if not subsets:
            assumptions.extend(
                (selected_symbol(rule_id), True) for rule_id in candidate_ids
            )
        candidate_indexes = {
            rule_id: index for index, rule_id in enumerate(candidate_ids)
        }
        coverages: dict[tuple[int, ...], Coverage] = {}
        seconds = 0.0
        stats = None
        collect_metrics = metric_enabled("clingo")
        try:
            start = net_time()
            with self.ctl.solve(
                yield_=True, assumptions=assumptions
            ) as handle:  # type: ignore
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
                    pos_mask, neg_mask = parse_coverage_symbol_masks(symbols)
                    selected = (
                        tuple(
                            sorted(
                                candidate_indexes[symbol.arguments[0].number]
                                for symbol in symbols
                                if symbol.name == SELECTED_PREDICATE
                                and len(symbol.arguments) == 1
                            )
                        )
                        if subsets
                        else tuple(range(len(program)))
                    )
                    coverage = coverages.setdefault(selected, Coverage([], []))
                    coverage.extend_masks(pos_mask, neg_mask)
                start = net_time()
            seconds += net_time() - start
            if collect_metrics:
                with instrumentation():
                    stats = self.ctl.statistics
        finally:
            self.activation.deactivate(self.ctl, active_rule_ids)
        phase = current_phase()
        add(f"{phase}.solving", seconds)
        self._record_solving(
            stats, seconds, len(program), len(coverages), subsets, phase
        )
        return coverages

    def _record_grounding(self, stats) -> None:
        if self._pending_grounding is None:
            return
        seconds, input_clauses, program_chars, phase = self._pending_grounding
        self._pending_grounding = None
        with instrumentation():
            grounded = ground_stats(stats)
            record_metric(
                "clingo",
                {
                    "operation": f"preground_{self.activation.name}",
                    "operation_category": "grounding",
                    "phase_context": phase,
                    "seconds": seconds,
                    "input_clauses": input_clauses,
                    "program_chars": program_chars,
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
        program_size: int,
        coverage_count: int,
        subsets: bool,
        phase: str,
    ) -> None:
        if stats is None:
            return
        with instrumentation():
            self._record_grounding(stats)
            models = clingo_stat(stats, "summary", "models", "enumerated")
            operation = "subset" if subsets else "fixed"
            record_metric(
                "clingo",
                {
                    "operation": f"{operation}_presolve_{self.activation.name}",
                    "operation_category": "solving",
                    "phase_context": phase,
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
