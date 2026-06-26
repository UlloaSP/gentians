import re
import itertools
import time

from ..asp.aggregate_analysis import (
    AggregateElement,
    contains_arithmetic,
    contains_comparison,
    get_aggregates,
    get_arithmetic_or_comparison_position,
)
from ..asp.answer_sets import from_as_to_list, from_list_to_as
from ..arguments import Arguments
from ..asp.clingo import ClingoInterface
from ..asp.rule_analysis import get_same_atoms, is_valid_rule
from ..timing import add, current_phase, record_metric
from ..asp.variable_placement_encoding import (
    VariablePlacementRules,
    generate_asp_program_for_combinations,
)


class VariablePlacer:
    def __init__(self, args: Arguments) -> None:
        self.args: Arguments = args
        # dict: hash of the asp program to place vars -> result, to avoid the
        # same computation
        self.already_encountered_asp_programs: "dict[int,list[list[list[int]]]]" = {}
        self.rules = VariablePlacementRules()

    def __reconstruct_clause(self, model: str, rule_stub: str) -> str:
        atoms = model.split(" ")

        r = rule_stub
        for el in atoms:
            position = int(el.split("(")[1][:-1])
            var = int(el.split("(")[0][1:])
            r = r.replace(f"_v{position:02d}_", f"V{var}")

        return r

    def _place_variables_clause(self, sampled_stub: str) -> "list[str]":
        """
        Replaces the wildcard with the variables in the clause.
        This now works with only 1 clause
        """
        res: "list[str]" = []
        placeholder = self.args.wildcard
        # number of positions to insert the variables
        n_positions: int = sampled_stub.count(placeholder)
        rv = self.args.max_variables  # deterministic is better
        single_variable_until_positions = _variable_placement_int(
            self.args, "single_variable_until_positions", 2
        )
        if n_positions <= single_variable_until_positions:
            n_variables = 1
        else:
            n_variables = rv

        n_vars_in_head = sampled_stub.split(":-")[0].count(placeholder)

        aggregates: "list[AggregateElement]" = []
        pos_arithm: "list[list[int]]" = []
        pos_comparison: "list[list[int]]" = []

        if "#" in sampled_stub:
            aggregates = get_aggregates(sampled_stub, placeholder)

        if contains_arithmetic(sampled_stub) or contains_comparison(sampled_stub):
            pos_arithm, pos_comparison = get_arithmetic_or_comparison_position(
                sampled_stub, placeholder
            )

        # Possible: improvements
        # 1) la variabile coinvolta in una ricorsione deve variare
        # es: a(X):- b(X), a(X).
        # 2) no variabili unsafe (quando c'è negazione)

        same_atoms, arity_same = get_same_atoms(
            sampled_stub, self.args.wildcard
        )

        asp_p = generate_asp_program_for_combinations(
            self.args,
            self.rules,
            n_positions,
            n_variables,
            n_vars_in_head,
            False,
            aggregates,
            pos_arithm=pos_arithm,
            pos_comparison=pos_comparison,
            same_atoms=same_atoms,
            arity_same_atoms=arity_same,
        )

        # generates the clause to fill
        for el in range(0, sampled_stub.count(placeholder)):
            sampled_stub = re.sub(
                re.escape(placeholder), f"_v{el:02d}_", sampled_stub, count=1
            )

        if hash(asp_p) in self.already_encountered_asp_programs:
            # already placed variables in an equivalent program,
            # retrieve it: I cannot store the clauses since the stub
            # is different, I need to reconstruct again the clause
            r = self.already_encountered_asp_programs[hash(asp_p)]
        else:
            clingo_arguments = _variable_placement_str_list(
                self.args, "clingo_arguments", ["0"]
            )
            asp_interface = ClingoInterface([asp_p], clingo_arguments)
            ctl = asp_interface.init_clingo_ctl()

            # answer_sets : 'list[str]' = []
            answer_sets_in_list: "list[list[list[int]]]" = []
            start_solving = time.perf_counter()
            models = 0
            with ctl.solve(yield_=True) as handle:  # type: ignore
                for m in handle:  # type: ignore
                    models += 1
                    a = str(m).split(" ")
                    a.sort()
                    a = " ".join(a)
                    # answer_sets.append(a)
                    answer_sets_in_list.append(from_as_to_list(str(a)))
                    # res.append(self.__reconstruct_clause(str(m), sampled_stub))
            seconds = time.perf_counter() - start_solving
            add("variable_placement.solving", seconds)
            record_metric(
                "clingo",
                {
                    "operation": "solving",
                    "phase_context": current_phase(),
                    "seconds": seconds,
                    "models": models,
                    "program_size": 1,
                    "coverage_subsets": 0,
                    "clingo_arguments": " ".join(clingo_arguments),
                },
            )

            answer_sets_in_list.sort()
            # remove duplicates
            r = list(k for k, _ in itertools.groupby(answer_sets_in_list))
            self.already_encountered_asp_programs[hash(asp_p)] = r

        # reconstruct the clause
        for rt in r:
            res.append(self.__reconstruct_clause(from_list_to_as(rt), sampled_stub))

        return res

    def place_variables_list_of_clauses(
        self, sampled_clauses: "list[str]"
    ) -> "list[list[str]]":
        """
        Loop to place the variable in all the sampled clauses
        """
        placed_list: "list[list[str]]" = []

        for index, clause in enumerate(sampled_clauses):
            start_clause = time.perf_counter()

            r = self._place_variables_clause(clause)

            valid_rules: "list[str]" = []
            pruned_count = 0
            if len(r) > 0:
                r.sort()
                for rl in r:
                    if is_valid_rule(rl):
                        valid_rules.append(rl)
                    else:
                        pruned_count += 1
                if len(valid_rules) > 0:
                    placed_list.append(valid_rules)

            record_metric(
                "candidate",
                {
                    "metric": "place_variables_clause",
                    "stub_index": index,
                    "stub": clause,
                    "seconds": time.perf_counter() - start_clause,
                    "variables_slots": clause.count(self.args.wildcard),
                    "body_literals": max(len(clause.split(":-")[-1].split(",")), 0),
                    "has_aggregate": "#" in clause,
                    "has_arithmetic": contains_arithmetic(clause),
                    "has_comparison": contains_comparison(clause),
                    "has_negation": "not " in clause,
                    "generated_placements": len(r),
                    "valid_placements": len(valid_rules),
                    "pruned_placements": pruned_count,
                },
            )

        return placed_list


def _variable_placement_int(args: Arguments, key: str, default: int) -> int:
    return int(args.variable_placement.get(key, default))


def _variable_placement_str_list(
    args: Arguments, key: str, default: list[str]
) -> list[str]:
    value = args.variable_placement.get(key, default)
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value]
    return list(default)
