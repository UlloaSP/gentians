from pathlib import Path

from .aggregate_analysis import AggregateElement
from ..arguments import Arguments


class VariablePlacementRules:
    def __init__(self) -> None:
        def get_content(filename: str) -> str:
            with open(Path(__file__).parents[1] / filename) as f:
                return f.read()

        self.base_rules = get_content("logic_programs/base_rules.lp")
        self.equal_rules = get_content("logic_programs/equal_rules.lp")
        self.rules_for_aggregates_arithm_comparison = get_content(
            "logic_programs/rules_for_aggregates_arithm_comparison.lp"
        )
        self.rules_for_aggregates = get_content(
            "logic_programs/rules_for_aggregates.lp"
        )
        self.rules_for_arithm = get_content("logic_programs/rules_for_arithm.lp")
        self.rules_for_comparison = get_content(
            "logic_programs/rules_for_comparison.lp"
        )
        self.rules_only_standard_atoms = get_content(
            "logic_programs/rules_only_standard_atoms.lp"
        )


def generate_asp_program_for_combinations(
    args: Arguments,
    rules: VariablePlacementRules,
    n_positions: int,
    n_variables: int,
    n_vars_in_head: int,
    to_find_max_number: bool = False,
    aggregates: "list[AggregateElement]" = [],
    pos_arithm: "list[list[int]]" = [],
    pos_comparison: "list[list[int]]" = [],
    same_atoms: "list[str]" = [],
    arity_same_atoms: int = 0,
) -> str:
    """
    Generate an answer set program to fill the holes in rules.
    to_find_max_number adds some rules to maximize the number
    of clauses. In this way we find the maximum number according
    to the constraints and avoid the generation of unused rules
    to compute the possible choices.
    TODO: improve the unsafety check (not trivial)
    """

    s: str = ""
    s += "% generate all the combinations of variables and positions\n"
    s += f"var(0..{n_variables - 1}).\n"
    s += f"pos(0..{n_positions - 1}).\n"
    s += "% last index for the variable in the head\n"
    s += f"last_index_var_in_head({n_vars_in_head - 1}).\n"

    s += rules.base_rules
    s += rules.equal_rules

    if len(aggregates) > 0 or len(pos_comparison) > 0 or len(pos_arithm) > 0:
        s += rules.rules_for_aggregates_arithm_comparison
    else:
        s += rules.rules_only_standard_atoms

    # to keep the compatibility with the previous version
    for i in range(n_variables):
        s += f"v{i}(I):- var_pos({i},I).\n"
        s += f"#show v{i}/1.\n"

    # s += "\n#show var_pos/2."

    # additional constraints coming from aggregates:
    # [Term: 1 - Atoms: 2 - Eq: 3] # the number denotes positions
    # X, Y : a(X,Y)
    # term : atom
    # i) all the terms must be different
    # ii) all the terms must appear in literals
    # iiiii) the result of the aggregate must be used: implicit in the constraint
    # imposing that no variables should appear only once

    if len(aggregates) > 0:
        s += rules.rules_for_aggregates
        s += "\n% constraints for aggregates\n"
        s += f"aggregate(0..{len(aggregates) - 1}).\n"
        for index, aggregate in enumerate(aggregates):
            last_i = -1
            for t in aggregate.position_var_terms:
                s += f"aggregate_term_position({index},{t}).\n"
            for a in aggregate.position_var_atom:
                s += f"aggregate_atom_position({index},{a}).\n"
                last_i = aggregate.position_var_atom[
                    len(aggregate.position_var_atom) - 1
                ]
            s += f"aggregate_result_position({index},{last_i + 1}).\n"

        if not args.unbalanced_aggregates:
            s += "\n% no global variables in tuple of aggregate elements\n"
            s += "not_agg_pos(P):- pos(P), not aggregate_term_position(_,P), not aggregate_atom_position(_,P).\n"
            s += ":- not_agg_pos(P), var_pos(V,P), aggregate_term_position(_,PosTermAgg), var_pos(V,PosTermAgg).\n"

    if len(pos_arithm) > 0:
        # the variables involved in arithmetic operators must be already defined
        # in another term
        s += rules.rules_for_arithm
        s += "\n% constraints for arithm operators\n"
        s += f"arithm(0..{len(pos_arithm) - 1}).\n"
        for index, el in enumerate(pos_arithm):
            for ii in range(0, len(el)):
                # if index > 0 and (index + 1) % 3 != 0:
                if (ii + 1) % 3 != 0:
                    # since in A + B = C, C can appear in the head
                    s += f"arithm_term_position({index},{el[ii]}).\n"
                else:
                    s += f"result_term_position({index},{el[ii]}).\n"
                s += f"all_arithm_term_position({index},{el[ii]}).\n"

    if len(pos_comparison) > 0:
        s += rules.rules_for_comparison
        s += "\n% constraints for comparison operators\n"
        s += f"comparison(0..{len(pos_comparison) - 1}).\n"
        for index, el in enumerate(pos_comparison):
            for v in el:
                s += f"comparison_term_position({index},{v}).\n"

    for v in same_atoms:
        s += v + "\n"

    return s
