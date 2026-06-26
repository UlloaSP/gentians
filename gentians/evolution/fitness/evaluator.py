from collections.abc import Callable

from ...asp.clingo import ClingoInterface
from ...rule_generation.program import Program
from ...timing import current_phase, record_metric


class FitnessEvaluator:
    def __init__(
        self,
        program: Program,
        max_as_to_generate_foreach_program: int,
        clingo_arguments: list[str],
        empty_score: float,
        fitness_operator: str,
        score_function: Callable[[float, float], float],
        combine_scores: Callable[[list[float]], float],
        select_best_by_score: bool,
    ) -> None:
        self.program = program
        self.max_as_to_generate_foreach_program = max_as_to_generate_foreach_program
        self.clingo_arguments = clingo_arguments
        self.empty_score = empty_score
        self.fitness_operator = fitness_operator
        self.score_function = score_function
        self.combine_scores = combine_scores
        self.select_best_by_score = select_best_by_score

    def evaluate_score(
        self, stub_indexes: "list[int]", prog_indexes: "list[int]", program: "list[str]"
    ) -> "tuple[float, bool, list[int]]":
        """
        Evaluates the score of an individual: first it computes the covered positive
        and negative for every subset of the clauses. Then, the score of every
        subset is defined as math.exp(covered_pos/tot_pos - covered_neg/tot_neg)*10.
        Simply considering the difference I think it is not enough (specially when
        there are few positive examples).
        The score of an individual is the average of the scores.
        """
        asp_solver = ClingoInterface(
            self.program.background,
            [f"{self.max_as_to_generate_foreach_program}", *self.clingo_arguments],
        )

        cov = asp_solver.extract_coverage_and_set_clauses(
            program,
            self.program.positive_examples,
            self.program.negative_examples,
            False,
        )

        best_found = False
        l_index: "list[int]" = []
        l_best_indexes: "list[str]" = []
        scored_subsets: "list[tuple[str, float]]" = []

        for res, element_coverage in cov.items():
            if res != "Error" and res != "Undefined":
                # set to remove duplicates
                cp: int = len(list(set(element_coverage.l_pos)))
                cn: int = len(list(set(element_coverage.l_neg)))

                # scores.append(math.exp((cp - cn)))
                v_pos = (
                    (cp / len(self.program.positive_examples))
                    if len(self.program.positive_examples) > 0
                    else 0
                )
                v_neg = (
                    (cn / len(self.program.negative_examples))
                    if len(self.program.negative_examples) > 0
                    else 0
                )
                score_value = self.score_function(v_pos, v_neg)
                scored_subsets.append((res, score_value))
                # consideration: here, [0,1] and [1,2] have the same score
                # where the first element is the covered positive and the
                # second is covered negative. However, is the first worst
                # than the second (the first only covers 1 negative example)
                # while the second two but it has one positive covered

                if cp == len(self.program.positive_examples) and cn == 0:
                    l_best_indexes.append(res)
                    best_found = True

        scores = [score for _, score in scored_subsets]

        score = self.combine_scores(scores) if scores else self.empty_score

        # if the best has not been found, still compute the current best
        # which is the one with the lowest associated cost. If two programs
        # have the same cost, pick the one with the lowest number of clauses.
        if not best_found:
            if self.select_best_by_score and scored_subsets:
                best_score = max(value for _, value in scored_subsets)
                l_best_indexes = [
                    key for key, value in scored_subsets if value == best_score
                ]
            else:
                current_min_el: str = next(iter(cov.keys()))
                for k, v in cov.items():
                    if v.get_cost() < cov[current_min_el].get_cost() or (
                        v.get_cost() == cov[current_min_el].get_cost()
                        and len(k) < len(current_min_el)
                    ):
                        current_min_el = k
                if current_min_el != "Undefined":
                    l_best_indexes = [current_min_el]

        # shortest one
        l_best_indexes.sort(key=lambda s: len(s))
        l_index = (
            [int(v) for v in list(l_best_indexes[0])] if len(l_best_indexes) > 0 else []
        )

        best_key = l_best_indexes[0] if l_best_indexes else ""
        best_coverage = cov.get(best_key)
        record_metric(
            "quality",
            {
                "metric": "evaluate_score",
                "phase_context": current_phase(),
                "program_size": len(program),
                "subsets_evaluated": len(cov),
                "score": score,
                "score_mean": sum(scores) / len(scores) if scores else self.empty_score,
                "score_max": max(scores) if scores else self.empty_score,
                "fitness_operator": self.fitness_operator,
                "best_found": best_found,
                "best_subset_size": len(l_index),
                "covered_positive": len(set(best_coverage.l_pos))
                if best_coverage is not None
                else 0,
                "covered_negative": len(set(best_coverage.l_neg))
                if best_coverage is not None
                else 0,
                "total_positive": len(self.program.positive_examples),
                "total_negative": len(self.program.negative_examples),
            },
        )

        return score, best_found, l_index
