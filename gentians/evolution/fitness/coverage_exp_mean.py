import math
from collections.abc import Callable

from ...asp.clingo import ClingoInterface
from ...rule_generation.program import Program
from ...timing import current_phase, record_metric


def coverage_exp_mean(
    program: Program,
    max_as_to_generate_foreach_program: int,
    clingo_arguments: list[str],
    empty_score: float,
) -> Callable[[list[int], list[int], list[str]], tuple[float, bool, list[int]]]:
    def evaluate_score(
        stub_indexes: list[int], prog_indexes: list[int], candidate_program: list[str]
    ) -> tuple[float, bool, list[int]]:
        asp_solver = ClingoInterface(
            program.background,
            [f"{max_as_to_generate_foreach_program}", *clingo_arguments],
        )
        cov = asp_solver.extract_coverage_and_set_clauses(
            candidate_program,
            program.positive_examples,
            program.negative_examples,
            False,
        )

        best_found = False
        l_best_indexes: list[str] = []
        scored_subsets: list[tuple[str, float]] = []

        for res, element_coverage in cov.items():
            if res == "Error" or res == "Undefined":
                continue
            cp = len(set(element_coverage.l_pos))
            cn = len(set(element_coverage.l_neg))
            v_pos = cp / len(program.positive_examples) if program.positive_examples else 0
            v_neg = cn / len(program.negative_examples) if program.negative_examples else 0
            scored_subsets.append((res, math.exp((v_pos - v_neg) * 10)))

            if cp == len(program.positive_examples) and cn == 0:
                l_best_indexes.append(res)
                best_found = True

        scores = [score for _, score in scored_subsets]
        score = sum(scores) / len(scores) if scores else empty_score

        if not best_found:
            current_min_el = next(iter(cov.keys()))
            for key, value in cov.items():
                current = cov[current_min_el]
                if value.get_cost() < current.get_cost() or (
                    value.get_cost() == current.get_cost()
                    and len(key) < len(current_min_el)
                ):
                    current_min_el = key
            if current_min_el != "Undefined":
                l_best_indexes = [current_min_el]

        l_best_indexes.sort(key=lambda s: len(s))
        l_index = [int(v) for v in list(l_best_indexes[0])] if l_best_indexes else []
        best_key = l_best_indexes[0] if l_best_indexes else ""
        best_coverage = cov.get(best_key)
        record_metric(
            "quality",
            {
                "metric": "evaluate_score",
                "phase_context": current_phase(),
                "program_size": len(candidate_program),
                "subsets_evaluated": len(cov),
                "score": score,
                "score_mean": sum(scores) / len(scores) if scores else empty_score,
                "score_max": max(scores) if scores else empty_score,
                "fitness_operator": "coverage_exp_mean",
                "best_found": best_found,
                "best_subset_size": len(l_index),
                "covered_positive": len(set(best_coverage.l_pos))
                if best_coverage is not None
                else 0,
                "covered_negative": len(set(best_coverage.l_neg))
                if best_coverage is not None
                else 0,
                "total_positive": len(program.positive_examples),
                "total_negative": len(program.negative_examples),
            },
        )
        return score, best_found, l_index

    return evaluate_score
