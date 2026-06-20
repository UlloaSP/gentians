import math

from ...asp.clingo import ClingoInterface
from ...rule_generation.program import Program


class FitnessEvaluator:
    def __init__(
        self, program: Program, max_as_to_generate_foreach_program: int
    ) -> None:
        self.program = program
        self.max_as_to_generate_foreach_program = max_as_to_generate_foreach_program

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
            [f"{self.max_as_to_generate_foreach_program}", "--project"],
        )

        cov = asp_solver.extract_coverage_and_set_clauses(
            program,
            self.program.positive_examples,
            self.program.negative_examples,
            False,
        )

        # print(cov)

        best_found = False
        l_index: "list[int]" = []
        l_best_indexes: "list[str]" = []
        scores: "list[float]" = []

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
                scores.append(math.exp((v_pos - v_neg) * 10))
                # consideration: here, [0,1] and [1,2] have the same score
                # where the first element is the covered positive and the
                # second is covered negative. However, is the first worst
                # than the second (the first only covers 1 negative example)
                # while the second two but it has one positive covered

                # print(self.positive_examples,self.negative_examples)
                # print(cp,cn)
                if cp == len(self.program.positive_examples):
                    if cn == 0:
                        print(f"Best found with indexes {res}")
                        print(program)
                        l_best_indexes.append(res)
                        best_found = True
                    # else:
                    #     print("Coverage 100% of the positive with")
                    # print([program[i] for i in l_index], cp, cn)

        # mean
        if len(scores) > 0:
            score = sum(scores) / len(scores)
        else:
            score = -2000

        # if the best has not been found, still compute the current best
        # which is the one with the lowest associated cost. If two programs
        # have the same cost, pick the one with the lowest number of clauses.
        if not best_found:
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
            [int(v) for v in list(l_best_indexes[0])]
            if len(l_best_indexes) > 0
            else []
        )

        return score, best_found, l_index
