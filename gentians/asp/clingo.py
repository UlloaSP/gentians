import clingo
import time
from pathlib import Path

from .callbacks import WrapperStopIfWarn
from .coverage import Coverage, generate_clauses_for_coverage_interpretations
from .stats import clingo_stat, ground_stats
from ..rule_generation.program import Example
from ..timing import add, current_phase, instrumentation, metric_enabled, record_metric

LOGIC_PROGRAMS = Path(__file__).parents[1] / "logic_programs"
COVERAGE_RULES = (LOGIC_PROGRAMS / "coverage_rules.lp").read_text()


class ClingoInterface:
    def __init__(
        self,
        lines: "list[str]",
        clingo_arguments: "list[str]",
        interpretation_pos: "list[Example]",
        interpretation_neg: "list[Example]",
    ) -> None:
        self.lines = lines
        self.clingo_arguments = clingo_arguments
        self.positive_examples = len(interpretation_pos)
        self.negative_examples = len(interpretation_neg)
        self.coverage_static_program = _build_coverage_static_program(
            self.lines, interpretation_pos, interpretation_neg
        )

    def extract_fixed_coverage(
        self,
        program: "list[str]",
    ) -> Coverage:
        """
        Extracts coverage for the full candidate program.
        """
        # TODO: aggiungere un flag per imporre che il programma abbia
        # come answer set solo quelli che gli sono stati passati come
        # esempi positivi

        generated_program = self.coverage_static_program + "\n" + "\n".join(program)

        wrp = WrapperStopIfWarn()
        ctl = clingo.Control(
            self.clingo_arguments, logger=wrp.wrapper_warn_undefined_callback
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
                        "operation": "grounding",
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

        if wrp.atom_undefined:
            # the program misses some atoms, so there is no need to
            # check for the coverage: ATTENTION: if the language bias is
            # not ok, this is a problem
            # print("Warning: undefined coverage")
            return Coverage([], [])

        coverage = Coverage([], [])

        start = time.perf_counter()
        models = 0
        collect_metrics = metric_enabled("clingo")
        with ctl.solve(yield_=True) as handle:  # type: ignore
            for m in handle:  # type: ignore
                if collect_metrics:
                    models += 1
                pos_mask, neg_mask = _parse_coverage_symbol_masks(m.symbols(shown=True))
                coverage.extend_masks(pos_mask, neg_mask)
        seconds = time.perf_counter() - start
        phase = current_phase()
        add(f"{phase}.solving", seconds)
        if collect_metrics:
            with instrumentation():
                record_metric(
                    "clingo",
                    {
                        "operation": "solving",
                        "operation_category": "solving",
                        "phase_context": phase,
                        "seconds": seconds,
                        "models": models,
                        "covered_positive": coverage.pos_mask.bit_count(),
                        "covered_negative": coverage.neg_mask.bit_count(),
                        "program_size": len(program),
                        "clingo_arguments": " ".join(self.clingo_arguments),
                        "stats_models_enumerated": clingo_stat(
                            ctl.statistics, "summary", "models", "enumerated"
                        ),
                        "stats_choices": clingo_stat(
                            ctl.statistics, "solving", "solvers", "choices"
                        ),
                        "stats_conflicts": clingo_stat(
                            ctl.statistics, "solving", "solvers", "conflicts"
                        ),
                    },
                )

        return coverage

def _build_coverage_static_program(
    background: "list[str]",
    interpretation_pos: "list[Example]",
    interpretation_neg: "list[Example]",
) -> str:
    parts: list[str] = []
    parts.extend(background)
    if len(interpretation_pos) > 0:
        parts.append(f"pos_exs(0..{len(interpretation_pos) - 1}).")
        parts.append(generate_clauses_for_coverage_interpretations(interpretation_pos, True))
    if len(interpretation_neg) > 0:
        parts.append(f"neg_exs(0..{len(interpretation_neg) - 1}).")
        parts.append(generate_clauses_for_coverage_interpretations(interpretation_neg, False))
    parts.append(COVERAGE_RULES)
    return "\n".join(parts)


def build_fixed_coverage_program(
    background: "list[str]",
    program: "list[str]",
    interpretation_pos: "list[Example]",
    interpretation_neg: "list[Example]",
) -> str:
    static_program = _build_coverage_static_program(
        background, interpretation_pos, interpretation_neg
    )
    return static_program + "\n" + "\n".join(str(rule) for rule in program)


def _parse_coverage_symbol_masks(symbols) -> tuple[int, int]:
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
