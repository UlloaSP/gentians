from ..rule_generation.program import Example
from ..rule_generation.parser import split_top_level_args


class Coverage:
    __slots__ = ("pos_mask", "neg_mask")

    def __init__(self, l_pos: "list[int]", l_neg: "list[int]"):
        self.pos_mask = _mask(l_pos)
        self.neg_mask = _mask(l_neg)

    def extend(self, l_pos: "list[int]", l_neg: "list[int]") -> None:
        self.pos_mask |= _mask(l_pos)
        self.neg_mask |= _mask(l_neg)

    def extend_masks(self, pos_mask: int, neg_mask: int) -> None:
        self.pos_mask |= pos_mask
        self.neg_mask |= neg_mask


def _mask(values: "list[int]") -> int:
    mask = 0
    for value in values:
        mask |= 1 << value
    return mask


def generate_clauses_for_coverage_interpretations(
    interpretations: list[Example], positive: bool
) -> str:
    """
    Generates the clauses for the ASP solver to check the coverage.
    TODO: alternative ({a,b},{c,d}) <=> a,b,not c, not d instead
    of two different rules.
    """
    parts: list[str] = []
    suffix: str = "cp" if positive else "cn"
    for cl_index, example in enumerate(interpretations):
        if len(example.included) > 0:
            parts.append(f"{suffix}i({cl_index}):- {example.included}.")

        if len(example.excluded) > 0:
            for atom in split_top_level_args(example.excluded):
                parts.append(f"{suffix}e({cl_index}):- {atom}.")

        if len(example.context) > 0:
            parts.append(example.context + ".")

    return "\n".join(parts) + "\n\n"
