import clingo
import time
from pathlib import Path

from .callbacks import WrapperStopIfWarn
from .coverage import Coverage, generate_clauses_for_coverage_interpretations
from ..rule_generation.program import Example
from ..timing import add, current_phase, record_metric

LOGIC_PROGRAMS = Path(__file__).parents[1] / "logic_programs"
COVERAGE_RULES = (LOGIC_PROGRAMS / "coverage_rules.lp").read_text()


class ClingoInterface:
    def __init__(self, lines: "list[str]", clingo_arguments: "list[str]") -> None:
        self.lines = lines
        self.clingo_arguments = clingo_arguments
        self._coverage_static_program_cache: dict[
            tuple[tuple[str, ...], tuple[str, ...]], str
        ] = {}

    def extract_fixed_coverage(
        self,
        program: "list[str]",
        interpretation_pos: "list[Example]",  # positive examples
        interpretation_neg: "list[Example]",  # negative examples
    ) -> Coverage:
        """
        Extracts coverage for the full candidate program.
        """
        # TODO: aggiungere un flag per imporre che il programma abbia
        # come answer set solo quelli che gli sono stati passati come
        # esempi positivi

        generated_program = self._coverage_static_program(
            interpretation_pos, interpretation_neg
        ) + "\n" + "\n".join(program)

        wrp = WrapperStopIfWarn()
        ctl = clingo.Control(
            self.clingo_arguments, logger=wrp.wrapper_warn_undefined_callback
        )  # type: ignore
        ctl.add("base", [], generated_program)
        start = time.perf_counter()
        ctl.ground([("base", [])])
        seconds = time.perf_counter() - start
        ground_stats = _ground_stats(ctl)
        phase = current_phase()
        add(f"{phase}.grounding", seconds)
        record_metric(
            "clingo",
            {
                "operation": "grounding",
                "operation_category": "grounding",
                "phase_context": phase,
                "seconds": seconds,
                "input_clauses": len(self.lines) + len(program),
                "program_chars": len(generated_program),
                "positive_examples": len(interpretation_pos),
                "negative_examples": len(interpretation_neg),
                "clingo_arguments": " ".join(self.clingo_arguments),
                "stats_atoms": ground_stats["atoms"],
                "stats_rules": ground_stats["rules"],
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
        with ctl.solve(yield_=True) as handle:  # type: ignore
            for m in handle:  # type: ignore
                models += 1
                l_cp, l_cn = _parse_coverage_symbols(m.symbols(shown=True))
                coverage.extend(l_cp, l_cn)
        seconds = time.perf_counter() - start
        phase = current_phase()
        add(f"{phase}.solving", seconds)
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
                "stats_models_enumerated": _clingo_stat(
                    ctl.statistics, "summary", "models", "enumerated"
                ),
                "stats_choices": _clingo_stat(
                    ctl.statistics, "solving", "solvers", "choices"
                ),
                "stats_conflicts": _clingo_stat(
                    ctl.statistics, "solving", "solvers", "conflicts"
                ),
            },
        )

        return coverage

    def _coverage_static_program(
        self,
        interpretation_pos: "list[Example]",
        interpretation_neg: "list[Example]",
    ) -> str:
        key = (
            tuple(str(example) for example in interpretation_pos),
            tuple(str(example) for example in interpretation_neg),
        )
        if key not in self._coverage_static_program_cache:
            self._coverage_static_program_cache[key] = _build_coverage_static_program(
                self.lines, interpretation_pos, interpretation_neg
            )
        return self._coverage_static_program_cache[key]


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


def _parse_coverage_symbols(symbols) -> "tuple[list[int],list[int]]":
    l_cp: list[int] = []
    l_cn: list[int] = []
    for symbol in symbols:
        if len(symbol.arguments) != 1:
            continue
        value = symbol.arguments[0].number
        if symbol.name == "extended_p":
            l_cp.append(value)
        elif symbol.name == "extended_n":
            l_cn.append(value)
    return l_cp, l_cn


def _clingo_stat(stats, *path: str) -> float:
    current = stats
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return 0.0
        current = current[key]
    return float(current) if isinstance(current, (int, float)) else 0.0


def _ground_stats(ctl) -> dict[str, float]:
    stats = ctl.statistics
    atoms = max(
        _clingo_stat(stats, "problem", "lp", "atoms"),
        _clingo_stat(stats, "problem", "lpStep", "atoms"),
    )
    if not atoms:
        atoms = float(sum(1 for _ in ctl.symbolic_atoms))
    rules = max(
        _clingo_stat(stats, "problem", "lp", "rules"),
        _clingo_stat(stats, "problem", "lpStep", "rules"),
    )
    return {"atoms": atoms, "rules": rules}
