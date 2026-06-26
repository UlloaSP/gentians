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
        self.safety_special_body = get_content("logic_programs/safety_special_body.lp")
        self.safety_ignore_aggregates = get_content(
            "logic_programs/safety_ignore_aggregates.lp"
        )
        self.safety_ignore_arithmetic = get_content(
            "logic_programs/safety_ignore_arithmetic.lp"
        )
        self.safety_ignore_comparison = get_content(
            "logic_programs/safety_ignore_comparison.lp"
        )
        self.safety_special_head_body = get_content(
            "logic_programs/safety_special_head_body.lp"
        )
        self.aggregate_global_tuple_constraint = get_content(
            "logic_programs/aggregate_global_tuple_constraint.lp"
        )
        self.atom_position_all = get_content("logic_programs/atom_position_all.lp")
        self.atom_position_special = get_content(
            "logic_programs/atom_position_special.lp"
        )
        self.atom_position_ignore_arithmetic = get_content(
            "logic_programs/atom_position_ignore_arithmetic.lp"
        )
        self.atom_position_ignore_comparison = get_content(
            "logic_programs/atom_position_ignore_comparison.lp"
        )


def generate_asp_program_for_combinations(
    args: Arguments,
    rules: VariablePlacementRules,
    n_positions: int,
    n_variables: int,
    n_vars_in_head: int,
    to_find_max_number: bool,
    aggregates: "list[AggregateElement]",
    pos_arithm: "list[list[int]]",
    pos_comparison: "list[list[int]]",
    same_atoms: "list[str]",
    arity_same_atoms: int,
) -> str:
    """
    Generate an answer set program to fill the holes in rules.
    to_find_max_number adds some rules to maximize the number
    of clauses. In this way we find the maximum number according
    to the constraints and avoid the generation of unused rules
    to compute the possible choices.
    TODO: improve the unsafety check (not trivial)
    """

    parts: list[str] = [
        "% generate all the combinations of variables and positions",
        f"var(0..{n_variables - 1}).",
        f"pos(0..{n_positions - 1}).",
        "% last index for the variable in the head",
        f"last_index_var_in_head({n_vars_in_head - 1}).",
    ]

    parts.append(rules.base_rules)
    if pos_arithm or pos_comparison:
        if pos_arithm:
            parts.append(rules.atom_position_ignore_arithmetic)
        if pos_comparison:
            parts.append(rules.atom_position_ignore_comparison)
        parts.append(rules.atom_position_special)
    else:
        parts.append(rules.atom_position_all)
    if same_atoms:
        parts.append(rules.equal_rules)

    if len(aggregates) > 0 or len(pos_comparison) > 0 or len(pos_arithm) > 0:
        parts.append(rules.safety_special_body)
        if aggregates:
            parts.append(rules.safety_ignore_aggregates)
        if pos_arithm:
            parts.append(rules.safety_ignore_arithmetic)
        if pos_comparison:
            parts.append(rules.safety_ignore_comparison)
        parts.append(rules.safety_special_head_body)
    else:
        parts.append(rules.rules_only_standard_atoms)

    # to keep the compatibility with the previous version
    for i in range(n_variables):
        parts.append(f"v{i}(I):- var_pos({i},I).")
        parts.append(f"#show v{i}/1.")

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
        parts.append(rules.rules_for_aggregates)
        parts.append("\n% constraints for aggregates")
        parts.append(f"aggregate(0..{len(aggregates) - 1}).")
        for index, aggregate in enumerate(aggregates):
            last_i = -1
            for t in aggregate.position_var_terms:
                parts.append(f"aggregate_term_position({index},{t}).")
            for a in aggregate.position_var_atom:
                parts.append(f"aggregate_atom_position({index},{a}).")
                last_i = aggregate.position_var_atom[
                    len(aggregate.position_var_atom) - 1
                ]
            parts.append(f"aggregate_result_position({index},{last_i + 1}).")

        if not args.unbalanced_aggregates:
            parts.append(rules.aggregate_global_tuple_constraint)

    if len(pos_arithm) > 0:
        # the variables involved in arithmetic operators must be already defined
        # in another term
        parts.append(rules.rules_for_arithm)
        parts.append("\n% constraints for arithm operators")
        parts.append(f"arithm(0..{len(pos_arithm) - 1}).")
        for index, el in enumerate(pos_arithm):
            for ii in range(0, len(el)):
                # if index > 0 and (index + 1) % 3 != 0:
                if (ii + 1) % 3 != 0:
                    # since in A + B = C, C can appear in the head
                    parts.append(f"arithm_term_position({index},{el[ii]}).")
                else:
                    parts.append(f"result_term_position({index},{el[ii]}).")
                parts.append(f"all_arithm_term_position({index},{el[ii]}).")

    if len(pos_comparison) > 0:
        parts.append(rules.rules_for_comparison)
        parts.append("\n% constraints for comparison operators")
        parts.append(f"comparison(0..{len(pos_comparison) - 1}).")
        for index, el in enumerate(pos_comparison):
            for v in el:
                parts.append(f"comparison_term_position({index},{v}).")

    for v in same_atoms:
        parts.append(v)

    return "\n".join(parts) + "\n"
