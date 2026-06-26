import re

from ..asp.rule_analysis import get_atoms

VAR_PATTERN = re.compile(r"V\d+")


class PlacedClause:
    """
    Class containing a clause.
    """

    def __init__(self, placed_clauses: "list[str]") -> None:
        self.placed_clauses = placed_clauses
        self.n_vars_clauses: "list[int]" = []
        self.n_atoms = 0

        for cl in self.placed_clauses:
            v = len(set(VAR_PATTERN.findall(cl)))
            self.n_vars_clauses.append(v)

        self.n_atoms += len(get_atoms(placed_clauses[0]))

    def __str__(self) -> str:
        s = ""
        for cl in self.placed_clauses:
            s += cl + "\n"
        s += f"n_vars: {self.n_vars_clauses}\nn_atoms: {self.n_atoms}\n"
        return s

    def __repr__(self) -> str:
        return self.__str__()
