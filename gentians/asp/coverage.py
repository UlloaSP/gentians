from ..rule_generation.program import Example
from ..rule_generation.parser import split_top_level_args


class Coverage:
    def __init__(self, l_pos: "list[int]", l_neg: "list[int]"):
        self.l_pos = l_pos
        self.l_neg = l_neg
        self.pos_mask = _mask(l_pos)
        self.neg_mask = _mask(l_neg)

    def get_cost(self) -> int:
        # if the best solution is not found, I compare the different programs
        # arising from one element. Here, I assume that the cost of covering
        # a positive example is -1 while the one of covering a negative is 1.
        # That is, the lowest is the score, the better is the program.
        # Thus, the cost of a solution is len(self.l_neg) - len(self.l_pos)
        return self.neg_mask.bit_count() - self.pos_mask.bit_count()

    def extend(self, l_pos: "list[int]", l_neg: "list[int]") -> None:
        self.l_pos.extend(l_pos)
        self.l_neg.extend(l_neg)
        self.pos_mask |= _mask(l_pos)
        self.neg_mask |= _mask(l_neg)


def _mask(values: "list[int]") -> int:
    mask = 0
    for value in values:
        mask |= 1 << value
    return mask


def generate_clauses_for_coverage_interpretations(
    interpretations: "list[Example]", positive: bool
) -> str:
    """
    Generates the clauses for the ASP solver to check the coverage.
    TODO: alternative ({a,b},{c,d}) <=> a,b,not c, not d instead
    of two different rules.
    """
    parts: list[str] = []
    suffix: str = "cp" if positive else "cn"
    cl_index = 0
    for example in interpretations:
        # inclusion
        if len(example.included) > 0:
            parts.append(f"{suffix}i({cl_index}):- {example.included}.")

            # if len(example.excluded) > 1:
            # exclusion
        if len(example.excluded) > 0:
            for atom in split_top_level_args(example.excluded):
                parts.append(f"{suffix}e({cl_index}):- {atom}.")

            # if len(example.) > 2:
            # context dependent examples
        if len(example.context) > 0:
            # for atom in atoms[2].split(' '):
            parts.append(example.context + ".")

        cl_index += 1

    return "\n".join(parts) + "\n\n"
