class AggregateElement:
    def __init__(
        self,
        position_var_terms: "list[int]",
        position_var_atom: "list[int]",
        var_eq: int,
    ) -> None:
        self.position_var_terms = position_var_terms
        self.position_var_atom = position_var_atom
        self.var_eq = var_eq  # for the variable after the = sign

    def __str__(self) -> str:
        return (
            "Term: "
            + " ".join([str(a) for a in self.position_var_terms])
            + " - Atoms: "
            + " ".join([str(a) for a in self.position_var_atom])
            + f" - Eq: {self.var_eq}"
        )

    def __repr__(self) -> str:
        return self.__str__()

    def __eq__(self, __value: object) -> bool:
        return (
            self.position_var_atom == __value.position_var_atom
            and self.var_eq == __value.var_eq
            and self.position_var_terms == __value.position_var_terms
        )


def get_aggregates(clause: str) -> "list[AggregateElement]":
    """
    Extracts the variables in the aggregates in the clause
    """
    # t_1, ..., t_k : \phi()
    # t1, ..., tk are terms
    # \phi is a literal
    # #sum{ _____,_____ : a  ( _____,_____ )} = _____, #sum{ _____,_____ : a  ( _____,_____ )} = _____
    # i need to return, a list of list. Each sublist contains the
    # variables in the terms
    open_brackets = [i for i, ch in enumerate(clause) if ch == "{"]
    closed_brackets = [i for i, ch in enumerate(clause) if ch == "}"]

    aggregates: "list[AggregateElement]" = []

    prev_pos = 0
    prev_count = 0
    for s, e in zip(open_brackets, closed_brackets):
        var_terms = []
        var_atom = []
        current_index = clause[prev_pos:s].count("_____") + prev_count
        aggr = clause[s + 1 : e]
        aggr = aggr.split(":")
        n_terms = aggr[0].count("_____")
        n_var_in_atom = aggr[1].count("_____")
        var_terms = list(range(current_index, n_terms + current_index))
        var_atom = list(
            range(current_index + n_terms, n_var_in_atom + current_index + n_terms)
        )

        # print(aggr)
        # print(f"current index: {current_index}")
        # print(f"var terms: {var_terms}")
        # print(f"var atom: {var_atom}")

        prev_pos = e
        prev_count = current_index + n_terms + n_var_in_atom

        aggregates.append(AggregateElement(var_terms, var_atom, prev_count))

    return aggregates


def contains_arithmetic(stub: str) -> bool:
    return any(op in stub for op in ["+", "-", "*", "/"])


def contains_comparison(stub: str) -> bool:
    return any(op in stub for op in [">", ">=", "<", "<=", "==", "!="])


def get_arithmetic_or_comparison_position(
    stub: str,
) -> tuple[list[list[int]], list[list[int]]]:
    """
    Extracts the positions of the variables involved in arithmetic or
    comparison operators.
    """
    els = stub.replace(" ", "").split("_____")
    pos_arithmetic: "list[list[int]]" = []
    pos_comparison: "list[list[int]]" = []
    for index, el in enumerate(els):
        if el in [">", ">=", "<", "<=", "==", "!="]:
            pos_comparison.append([index - 1, index])

        if el in ["+", "-", "*", "/"]:
            pos_arithmetic.append([index - 1, index, index + 1])

    return pos_arithmetic, pos_comparison
