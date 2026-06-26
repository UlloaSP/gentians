import clingo
import time

from .callbacks import wrapper_exit_callback, WrapperStopIfWarn
from .coverage import Coverage, generate_clauses_for_coverage_interpretations
from ..rule_generation.program import Example
from ..timing import add, current_phase, record_metric


class ClingoInterface:
    def __init__(self, lines: "list[str]", clingo_arguments: "list[str]") -> None:
        self.lines = lines
        self.clingo_arguments = clingo_arguments

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
    ) -> "dict[str,Coverage]":
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

        generated_program = _build_coverage_program(
            self.lines,
            program,
            interpretation_pos,
            interpretation_neg,
            fixed,
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
            return {"Undefined": Coverage([], [])}

        # res = str(ctl.solve())
        # answer_sets : 'list[str] '= []

        # key: rule_id (string containing the selected rules)
        # value: tuple(covered_pos, covered_neg)
        # needed since I need to check that NO answer sets cover
        # negative examples.
        comb_rules: "dict[str,Coverage]" = {}

        start = time.perf_counter()
        models = 0
        with ctl.solve(yield_=True) as handle:  # type: ignore
            for m in handle:  # type: ignore
                models += 1
                l_rules, l_cp, l_cn = _parse_coverage_answer_set(str(m))
                if fixed:
                    # needed since for fixed there are no r/1 atoms
                    l_rules = [i for i in range(len(program))]
                _merge_coverage_result(comb_rules, l_rules, l_cp, l_cn)
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


def _build_coverage_program(
    background: "list[str]",
    program: "list[str]",
    interpretation_pos: "list[Example]",
    interpretation_neg: "list[Example]",
    fixed: bool,
) -> str:
    parts: list[str] = []
    parts.extend(background)
    parts.extend(_candidate_program_clauses(program, fixed))
    if len(interpretation_pos) > 0:
        parts.append(f"pos_exs(0..{len(interpretation_pos)}).")
        parts.append(generate_clauses_for_coverage_interpretations(interpretation_pos, True))
    if len(interpretation_neg) > 0:
        parts.append(f"neg_exs(0..{len(interpretation_neg)}).")
        parts.append(generate_clauses_for_coverage_interpretations(interpretation_neg, False))
    parts.append(
        """
        extended_p(I):- pos_exs(I), cpi(I), not cpe(I).
        extended_n(I):- neg_exs(I), cni(I), not cne(I).

        total_extended_p(N):- N = #count{X : extended_p(X)}.
        total_extended_n(N):- N = #count{X : extended_n(X)}.

        #show extended_p/1.
        #show extended_n/1.

        #show total_extended_p/1.
        #show total_extended_n/1.
        """
    )
    if not fixed:
        parts.append("#show r/1.")
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


def _parse_coverage_answer_set(answer_set: str) -> "tuple[list[int],list[int],list[int]]":
    l_rules: list[int] = []
    l_cp: list[int] = []
    l_cn: list[int] = []
    for atom in answer_set.split(" "):
        if atom.startswith("r"):
            l_rules.append(int(atom.split("r(")[1][:-1]))
        elif atom.startswith("extended_p"):
            l_cp.append(int(atom.split("extended_p(")[1][:-1]))
        elif atom.startswith("extended_n"):
            l_cn.append(int(atom.split("extended_n(")[1][:-1]))
    return l_rules, l_cp, l_cn


def _merge_coverage_result(
    comb_rules: "dict[str,Coverage]",
    l_rules: "list[int]",
    l_cp: "list[int]",
    l_cn: "list[int]",
) -> None:
    dict_key = "".join(str(index) for index in l_rules)
    if dict_key in comb_rules:
        # this solution also considers duplicates
        comb_rules[dict_key].l_pos.extend(l_cp)
        comb_rules[dict_key].l_neg.extend(l_cn)
    else:
        comb_rules[dict_key] = Coverage(l_cp, l_cn)


def _clingo_stat(stats, *path: str) -> float:
    current = stats
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return 0.0
        current = current[key]
    return float(current) if isinstance(current, (int, float)) else 0.0
