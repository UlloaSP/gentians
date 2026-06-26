import random
import copy
import itertools  # to generate unbalanced aggregates

from ..arguments import Arguments
from ..console import print_error_and_exit
from .program import ModeDeclaration
from .sampled_clause import Clause, Literal


class ProgramSampler:
    def __init__(
        self,
        language_bias_head: "list[ModeDeclaration]",
        language_bias_body: "list[ModeDeclaration]",
        args: Arguments,
    ) -> None:
        self.args: Arguments = args
        self.language_bias_head: "list[ModeDeclaration]" = language_bias_head
        self.language_bias_body: "list[ModeDeclaration]" = language_bias_body

        # # True if we are sampling for a constraint, changed every iteration
        self.body_constraint: bool = False

        # enable recursion: super carefully with aggregates since this may
        # cause loops: for instance, this program loops
        # {el(1,2)}.
        # s1(V0):- V2+V1=V0,s0(V1),s1(V2).
        # s0(V0):- #sum{V2,V1:el(V1,V2)}=V0.
        # s1(V0):-  #sum{V2,V1:el(V1,V2)}=V0,#sum{V2,V1:el(V2,V1)}=V0.
        self.enable_recursion = _sampling_bool(self.args, "enable_recursion")

        # store the already placed clauses to avoid recomputation
        # removed since all the clauses are different
        # self.stub_placed_dict : 'dict[str,list[str]]' = {}

        if self.args.aggregates:
            for el in self.args.aggregates:
                # compute the cartesian product between aggregates and body atoms
                # ex: modeb a/1 and b/1 and aggregates #sum e #count i get
                # #sum{X : a(X)} #count{X : a(X)} #sum{X : b(X)} #count{X : b(X)}
                # self.language_bias_body.append(ModeDeclaration(("1",f"__{el}","1","positive"), False))
                md = ModeDeclaration(("1", "", "1", "positive"), False)
                md.add_aggregate(el)
                self.language_bias_body.append(copy.deepcopy(md))

        # sys.exit()
        if self.args.arithmetic_operators:
            for el in self.args.arithmetic_operators:
                # self.body_literals.append(Literal(f"__{el}__",3,1,False))
                # self.language_bias_body.append(ModeDeclaration(("1",f"__{el}__","3","positive"), False))
                md = ModeDeclaration(("1", f"__{el}__", "3", "positive"), False)
                md.arithmetic_operator = el
                self.language_bias_body.append(copy.deepcopy(md))

        if self.args.comparison_operators:
            for el in self.args.comparison_operators:
                # self.body_literals.append(Literal(f"__{el}__",2,1,False))
                # self.language_bias_body.append(ModeDeclaration(("1",f"__{el}__","2","positive"), False))
                md = ModeDeclaration(("1", f"__{el}__", "2", "positive"), False)
                md.comparison_operator = el
                self.language_bias_body.append(copy.deepcopy(md))

    def __replace_operators(self, body: "list[Literal]") -> "list[list[str]]":
        """
        Replaces the placeholder names with the comparison or arithmetic operator.
        """
        body_literals: "list[str]" = []
        aggregates_indexes: list[int] = []
        all_aggregates: "list[list[str]]" = []
        placeholder = self.args.wildcard
        to_append: str = ""

        for i, el in enumerate(body):
            to_append = self.__render_comparison(el, placeholder)
            if to_append == "":
                to_append = self.__render_arithmetic(el, placeholder)
            if to_append == "" and el.mode_bias.aggregation_function != "":
                aggregate = self.__render_aggregate(el, placeholder)
                if isinstance(aggregate, list):
                    all_aggregates.append(aggregate)
                else:
                    to_append = aggregate

                aggregates_indexes.append(i)
            elif to_append == "":
                to_append = el.get_stub_representation(self.args.wildcard)

            # append the literal to the body
            if to_append != "":
                body_literals.append(to_append)

        nb: "list[list[str]]" = []
        for agg_comb in itertools.product(*all_aggregates):
            cb = body_literals[:]
            for agg, index in zip(agg_comb, aggregates_indexes):
                cb[index] = agg
            nb.append(cb)

        return nb

    def __render_comparison(self, literal: Literal, placeholder: str) -> str:
        operators = {
            "lt": "<",
            "leq": "<=",
            "gt": ">",
            "geq": ">=",
            "eq": "==",
            "neq": "!=",
        }
        operator = operators.get(literal.mode_bias.comparison_operator)
        return f"{placeholder}{operator}{placeholder}" if operator else ""

    def __render_arithmetic(self, literal: Literal, placeholder: str) -> str:
        operators = {
            "add": "+",
            "sub": "-",
            "mul": "*",
            "div": "/",
        }
        if literal.mode_bias.arithmetic_operator == "abs":
            return f"|{placeholder}-{placeholder}|={placeholder}"
        operator = operators.get(literal.mode_bias.arithmetic_operator)
        return (
            f"{placeholder}{operator}{placeholder}={placeholder}"
            if operator
            else ""
        )

    def __render_aggregate(
        self, literal: Literal, placeholder: str
    ) -> "str | list[str]":
        total_number_of_variables = sum(
            int(x[1]) for x in literal.mode_bias.aggregation_atoms
        )
        if not self.args.unbalanced_aggregates:
            return self.__render_aggregate_with_arity(
                literal, placeholder, total_number_of_variables
            )
        return [
            self.__render_aggregate_with_arity(literal, placeholder, current_arity)
            for current_arity in range(1, total_number_of_variables + 1)
        ]

    def __render_aggregate_with_arity(
        self, literal: Literal, placeholder: str, tuple_arity: int
    ) -> str:
        ph = ",".join([placeholder] * tuple_arity)
        atoms_in_agg: "list[str]" = []
        for name, arity in literal.mode_bias.aggregation_atoms:
            ph_atom = ",".join([placeholder] * int(arity))
            atoms_in_agg.append(f"{name}({ph_atom})")
        return (
            "#"
            + literal.mode_bias.aggregation_function
            + "{"
            + ph
            + ":"
            + ",".join(atoms_in_agg)
            + "}="
            + placeholder
        )

    def __sample_level_distr_recall(
        self, available_atoms: "list[ModeDeclaration]", recalls: "list[int]"
    ) -> "Literal|None":
        """
        Randomly samples an element if the recall is not 0
        """
        weights = [1 if idx > 0 else 0 for idx in recalls]
        if not any(weights):
            # all zeros
            return None
        sampled_literal_pos = random.choices(range(len(available_atoms)), weights, k=1)[
            0
        ]
        negation_probability = _sampling_float(self.args, "negation_probability")
        negated = random.random() < negation_probability and (
            not available_atoms[sampled_literal_pos].positive
        )

        return copy.deepcopy(
            Literal(
                copy.deepcopy(available_atoms[sampled_literal_pos]),
                negated,
                sampled_literal_pos,
            )
        )

    def __sample_literals_list(
        self, literals_list: "list[ModeDeclaration]", head: bool
    ) -> "list[Literal]":
        """
        Samples a list of literals to be used in either in the head
        or in the body.
        head: True if the sampling is for the head of the rule (to allow constraints)
        body_constraint: True if the sampling is for a constraint (to
            discard the possibility to sample constraints with a single
            atom, i.e., :- a(_).)
        """
        # list_indexes_sampled_literals : 'list[Literal]' = [] # indexes
        sampled_list: "list[Literal]" = []
        depth = 0
        stop = (random.random() > self.args.prob_increase) if head else False
        max_depth_head = self.args.disjunctive_head_length
        recalls: "list[int]" = [x.recall for x in literals_list]

        while (not stop) and (depth < self.args.max_depth) and (max_depth_head > 0):
            sampled_literal = self.__sample_level_distr_recall(literals_list, recalls)
            if sampled_literal is None:
                stop = True
            else:
                recalls[sampled_literal.index_in_mode_bias_list] -= 1
                sampled_list.append(sampled_literal)
                # here we are in the body of a constraint: we need at least 2 atoms
                if self.body_constraint and depth == 0:
                    stop = False
                else:
                    stop = random.random() > self.args.prob_increase
                depth += 1
            if head:
                max_depth_head -= 1
        return sampled_list

    def sample_clauses_stub(self, how_many: int) -> "list[Clause]":
        """
        Samples how_many clauses.
        """
        original_depth: int = self.args.max_depth
        clauses: "list[Clause]" = []

        for _ in range(0, how_many):
            body: "list[Literal]" = []
            head: "list[Literal]" = []

            if len(self.language_bias_head) > 0:
                head = self.__sample_literals_list(
                    self.language_bias_head, True
                )  # true allows constraints
                self.body_constraint = len(head) == 0

            # decrease the depth since we already sampled atoms for the head
            self.args.max_depth -= len(head)

            body = self.__sample_literals_list(self.language_bias_body, False)

            # replace __lt__, __gt__, __eq__, __neq__, __add__, __sub__, __mul__
            body_list = self.__replace_operators(body)

            if self.enable_recursion:
                print_error_and_exit("self.enable_recursion not yet implemented.")

            current_clause: "Clause" = Clause(head, body, [])
            head_set = set(head)
            for b in body_list:
                body_set = set(b)
                subs_h = head_set.issubset(body_set) and len(head_set) > 0
                subs_b = body_set.issubset(head_set) and len(body_set) > 0
                is_valid = not (subs_h or subs_b)
                if is_valid:
                    head_as_str: str = ";".join(
                        sorted(
                            [
                                x.get_stub_representation(self.args.wildcard)
                                for x in head
                            ]
                        )
                    )
                    body_as_str: str = ",".join(sorted(b))
                    cl = f"{head_as_str} :- {body_as_str}."
                    current_clause.instantiated.append(cl)

            if current_clause not in clauses:
                # avoid duplicates
                clauses.append(copy.deepcopy(current_clause))

            self.args.max_depth = original_depth

        return clauses


def _sampling_value(args: Arguments, key: str) -> object:
    if key not in args.sampling:
        raise ValueError(f"Missing sampling config key: {key}")
    return args.sampling[key]


def _sampling_float(args: Arguments, key: str) -> float:
    return float(_sampling_value(args, key))


def _sampling_bool(args: Arguments, key: str) -> bool:
    value = _sampling_value(args, key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on"}
    return bool(value)
