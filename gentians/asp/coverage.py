from ..rule_generation.program import Example


class Coverage:
    def __init__(self, l_pos: "list[int]" = [], l_neg: "list[int]" = []):
        self.l_pos = l_pos
        self.l_neg = l_neg

    def get_cost(self) -> int:
        # if the best solution is not found, I compare the different programs
        # arising from one element. Here, I assume that the cost of covering
        # a positive example is -1 while the one of covering a negative is 1.
        # That is, the lowest is the score, the better is the program.
        # Thus, the cost of a solution is len(self.l_neg) - len(self.l_pos)
        return len(self.l_neg) - len(self.l_pos)

    def __str__(self) -> str:
        return (
            "-> Positive: "
            + ",".join([str(x) for x in self.l_pos])
            + " - Negative: "
            + ",".join([str(x) for x in self.l_neg])
            + " <-"
        )

    def __repr__(self) -> str:
        return self.__str__()


def generate_clauses_for_coverage_interpretations(
    interpretations: "list[Example]", positive: bool
) -> str:
    """
    Generates the clauses for the ASP solver to check the coverage.
    TODO: alternative ({a,b},{c,d}) <=> a,b,not c, not d instead
    of two different rules.
    """
    generated_str: str = ""
    suffix: str = "cp" if positive else "cn"
    cl_index = 0
    # print(interpretations)
    for example in interpretations:
        # inclusion
        if len(example.included) > 0:
            r = f"{suffix}i({cl_index}):- {example.included}.\n"
            generated_str += r

            # if len(example.excluded) > 1:
            # exclusion
        if len(example.excluded) > 0:
            # for atom in atoms[1].split(' '):
            r = f"{suffix}e({cl_index}):- {example.excluded}.\n"
            generated_str += r

            # if len(example.) > 2:
            # context dependent examples
            if len(example.context) > 0:
                # for atom in atoms[2].split(' '):
                generated_str += example.context + ".\n"

        cl_index += 1
    generated_str += "\n"

    return generated_str
