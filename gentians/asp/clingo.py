import clingo
import time
from pathlib import Path

from .callbacks import wrapper_exit_callback, WrapperStopIfWarn
from .coverage import Coverage, generate_clauses_for_coverage_interpretations
from ..rule_generation.program import Example
from ..timing import add, current_phase, record_metric

CoverageKey = tuple[int, ...]
LOGIC_PROGRAMS = Path(__file__).parents[1] / "logic_programs"
COVERAGE_RULES = (LOGIC_PROGRAMS / "coverage_rules.lp").read_text()
COVERAGE_SHOW_SELECTED_RULES = (
    LOGIC_PROGRAMS / "coverage_show_selected_rules.lp"
).read_text()


class ClingoInterface:
    def __init__(self, lines: "list[str]", clingo_arguments: "list[str]") -> None:
        self.lines = lines
        self.clingo_arguments = clingo_arguments
        self._coverage_static_program_cache: dict[
            tuple[tuple[str, ...], tuple[str, ...], bool], str
        ] = {}

    # TODO: cambiare questione coverage
    def init_clingo_ctl(self) -> "clingo.Control":
        """
        Init clingo and grounds the program
        """
        ctl = clingo.Control(self.clingo_arguments, logger=wrapper_exit_callback)
        try:
            for clause in self.lines:
                ctl.add("base", [], clause)
            start = time.perf_counter()
            ctl.ground([("base", [])])
            seconds = time.perf_counter() - start
            phase = current_phase()
            add(f"{phase}.grounding", seconds)
            record_metric(
                "clingo",
                {
                    "operation": "grounding",
                    "phase_context": phase,
                    "seconds": seconds,
                    "input_clauses": len(self.lines),
                    "clingo_arguments": " ".join(self.clingo_arguments),
                },
            )
        except RuntimeError:
            print("Syntax error, parsing failed.")

        return ctl

    def extract_coverage_and_set_clauses(
        self,
        program: "list[str]",
        interpretation_pos: "list[Example]",  # positive examples
        interpretation_neg: "list[Example]",  # negative examples
        fixed: bool,
        stop_on_best: bool = False,
    ) -> "dict[CoverageKey,Coverage]":
        """
        Extracts the coverage for every subset of clauses.
        """
        # l_results : 'list[tuple[int,int,list[int]]]' = []
        # TODO: ora fisso il numero massimo di clausole e il
        # solver ASP mi dice quale combinazione è la migliore.
        # Potrei invece (da fare) considerare iterativamente un
        # numero di clausole maggiore.
        # TODO: aggiungere un flag per imporre che il programma abbia
        # come answer set solo quelli che gli sono stati passati come
        # esempi positivi

        # print("Extract coverage")
        # print(program)
        # print("----- HERE -----")
        # print('FISSATO')
        # program = ["red(X) ; green(X) ; blue(X) :- node(X).", ":- e(X,Y), red(X), red(Y).", ":- e(X,Y), green(X), green(Y).", ":- e(X,Y), blue(X), blue(Y)."]

        generated_program = (
            self._coverage_static_program(
                interpretation_pos, interpretation_neg, fixed
            )
            + "\n"
            + "\n".join(_candidate_program_clauses(program, fixed))
        )

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
        record_metric(
            "clingo",
            {
                "operation": "grounding",
                "phase_context": phase,
                "seconds": seconds,
                "input_clauses": len(self.lines) + len(program),
                "program_chars": len(generated_program),
                "positive_examples": len(interpretation_pos),
                "negative_examples": len(interpretation_neg),
                "clingo_arguments": " ".join(self.clingo_arguments),
                "stats_atoms": _clingo_stat(ctl.statistics, "problem", "lp", "atoms"),
                "stats_rules": _clingo_stat(ctl.statistics, "problem", "lp", "rules"),
            },
        )

        if wrp.atom_undefined:
            # the program misses some atoms, so there is no need to
            # check for the coverage: ATTENTION: if the language bias is
            # not ok, this is a problem
            # print("Warning: undefined coverage")
            return {}

        # res = str(ctl.solve())
        # answer_sets : 'list[str] '= []

        # key: rule_id (string containing the selected rules)
        # value: tuple(covered_pos, covered_neg)
        # needed since I need to check that NO answer sets cover
        # negative examples.
        comb_rules: "dict[CoverageKey,Coverage]" = {}

        start = time.perf_counter()
        models = 0
        all_pos_mask = (1 << len(interpretation_pos)) - 1
        with ctl.solve(yield_=True) as handle:  # type: ignore
            for m in handle:  # type: ignore
                models += 1
                l_rules, l_cp, l_cn = _parse_coverage_symbols(m.symbols(shown=True))
                if fixed:
                    # needed since for fixed there are no r/1 atoms
                    l_rules = [i for i in range(len(program))]
                coverage = _merge_coverage_result(comb_rules, l_rules, l_cp, l_cn)
                if (
                    stop_on_best
                    and coverage.pos_mask == all_pos_mask
                    and coverage.neg_mask == 0
                ):
                    handle.cancel()
                    break
        seconds = time.perf_counter() - start
        phase = current_phase()
        add(f"{phase}.solving", seconds)
        record_metric(
            "clingo",
            {
                "operation": "solving",
                "phase_context": phase,
                "seconds": seconds,
                "models": models,
                "coverage_subsets": len(comb_rules),
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

        return comb_rules

    def _coverage_static_program(
        self,
        interpretation_pos: "list[Example]",
        interpretation_neg: "list[Example]",
        fixed: bool,
    ) -> str:
        key = (
            tuple(str(example) for example in interpretation_pos),
            tuple(str(example) for example in interpretation_neg),
            fixed,
        )
        if key not in self._coverage_static_program_cache:
            self._coverage_static_program_cache[key] = _build_coverage_static_program(
                self.lines, interpretation_pos, interpretation_neg, fixed
            )
        return self._coverage_static_program_cache[key]


def _build_coverage_static_program(
    background: "list[str]",
    interpretation_pos: "list[Example]",
    interpretation_neg: "list[Example]",
    fixed: bool,
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
    if not fixed:
        parts.append(COVERAGE_SHOW_SELECTED_RULES)
    return "\n".join(parts)


def _candidate_program_clauses(program: "list[str]", fixed: bool) -> "list[str]":
    clauses: list[str] = []
    for cl_index, clause in enumerate(program):
        if fixed:
            clauses.append(clause)
        else:
            r = f"r({cl_index})"
            clauses.append(clause[:-1] + f", {r}.")
            clauses.append("{" + r + "}.")
    return clauses


def _parse_coverage_symbols(symbols) -> "tuple[list[int],list[int],list[int]]":
    l_rules: list[int] = []
    l_cp: list[int] = []
    l_cn: list[int] = []
    for symbol in symbols:
        if len(symbol.arguments) != 1:
            continue
        value = symbol.arguments[0].number
        if symbol.name == "r":
            l_rules.append(value)
        elif symbol.name == "extended_p":
            l_cp.append(value)
        elif symbol.name == "extended_n":
            l_cn.append(value)
    return l_rules, l_cp, l_cn


def _merge_coverage_result(
    comb_rules: "dict[CoverageKey,Coverage]",
    l_rules: "list[int]",
    l_cp: "list[int]",
    l_cn: "list[int]",
) -> Coverage:
    dict_key = tuple(sorted(l_rules))
    if dict_key in comb_rules:
        # this solution also considers duplicates
        comb_rules[dict_key].extend(l_cp, l_cn)
    else:
        comb_rules[dict_key] = Coverage(l_cp, l_cn)
    return comb_rules[dict_key]


def _clingo_stat(stats, *path: str) -> float:
    current = stats
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return 0.0
        current = current[key]
    return float(current) if isinstance(current, (int, float)) else 0.0
