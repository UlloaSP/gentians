import math
from collections.abc import Callable

from .coverage_common import (
    best_subset_by_lowest_cost,
    coverage_rates,
    covers_all_positive_no_negative,
    extract_program_coverage,
    record_fitness_metric,
    shortest_subset_indexes,
)
from ...rule_generation.program import Program


def coverage_exp_mean(
    program: Program,
    max_as_to_generate_foreach_program: int,
    clingo_arguments: list[str],
    empty_score: float,
) -> Callable[[list[int], list[int], list[str]], tuple[float, bool, list[int]]]:
    def evaluate_score(
        stub_indexes: list[int], prog_indexes: list[int], candidate_program: list[str]
    ) -> tuple[float, bool, list[int]]:
        cov = extract_program_coverage(
            program,
            candidate_program,
            max_as_to_generate_foreach_program,
            clingo_arguments,
        )

        best_found = False
        l_best_indexes: list[str] = []
        scored_subsets: list[tuple[str, float]] = []

        for res, element_coverage in cov.items():
            if res == "Error" or res == "Undefined":
                continue
            rates = coverage_rates(program, element_coverage)
            scored_subsets.append(
                (res, math.exp((rates.positive_rate - rates.negative_rate) * 10))
            )

            if covers_all_positive_no_negative(program, rates):
                l_best_indexes.append(res)
                best_found = True

        scores = [score for _, score in scored_subsets]
        score = sum(scores) / len(scores) if scores else empty_score

        if not best_found:
            l_best_indexes = best_subset_by_lowest_cost(cov)

        l_index = shortest_subset_indexes(l_best_indexes)
        best_key = l_best_indexes[0] if l_best_indexes else ""
        record_fitness_metric(
            "coverage_exp_mean",
            program,
            candidate_program,
            cov,
            scores,
            score,
            empty_score,
            best_found,
            l_index,
            best_key,
        )
        return score, best_found, l_index

    return evaluate_score
