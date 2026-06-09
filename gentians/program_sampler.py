import random
import copy
import random
import sys
import itertools # to generate unbalanced aggregates

from .arguments import Arguments
from .utils import UNDERSCORE_SIZE, print_error_and_exit
from .parser import ModeDeclaration


class Literal:
    def __init__(self,
            mode_bias : ModeDeclaration,
            negated : bool,
            index_in_mode_bias_list : int
        ) -> None:
        self.mode_bias : ModeDeclaration = mode_bias
        self.negated : bool = negated
        self.index_in_mode_bias_list : int = index_in_mode_bias_list

    def get_stub_representation(self) -> str:
        """
        Returns the string representation of the mode declaration.
        """
        s = self.mode_bias.name
        if self.mode_bias.arity > 0:
            s += '('
            for i in range(0, self.mode_bias.arity):
                s += ('_' * UNDERSCORE_SIZE) + ','
            s = s[:-1] + ')'
        return s if (not self.negated) else f"not {s}"

    def __str__(self) -> str:
        return f"{'negated' if self.negated else ''} {self.mode_bias}"
    def __repr__(self) -> str:
        return self.__str__()

class Clause:
    def __init__(self, head : 'list[Literal]', body : 'list[Literal]', instantiated : 'list[str]') -> None:
        self.head : 'list[Literal]' = head
        self.body : 'list[Literal]' = body
        self.instantiated : 'list[str]' = instantiated
    
    def __eq__(self, value: object) -> bool:
        return sorted(self.instantiated) == sorted(value.instantiated)
    def __str__(self) -> str:
        return f"head:{self.head} - body:{self.body}"
    def __repr__(self) -> str:
        return self.__str__()

class ProgramSampler:
    def __init__(
            self,
            language_bias_head : 'list[ModeDeclaration]',
            language_bias_body : 'list[ModeDeclaration]',
            args : Arguments
        ) -> None:
        self.args : Arguments = args
        self.language_bias_head : 'list[ModeDeclaration]' = language_bias_head
        self.language_bias_body : 'list[ModeDeclaration]' = language_bias_body
        
        # # True if we are sampling for a constraint, changed every iteration
        self.body_constraint : bool = False
        
        # enable recursion: super carefully with aggregates since this may
        # cause loops: for instance, this program loops
        # {el(1,2)}.
        # s1(V0):- V2+V1=V0,s0(V1),s1(V2).
        # s0(V0):- #sum{V2,V1:el(V1,V2)}=V0.
        # s1(V0):-  #sum{V2,V1:el(V1,V2)}=V0,#sum{V2,V1:el(V2,V1)}=V0.
        self.enable_recursion = False

        # store the already placed clauses to avoid recomputation
        # removed since all the clauses are different
        # self.stub_placed_dict : 'dict[str,list[str]]' = {}
        
        if self.args.aggregates:
            for el in self.args.aggregates:
                # compute the cartesian product between aggregates and body atoms
                # ex: modeb a/1 and b/1 and aggregates #sum e #count i get
                # #sum{X : a(X)} #count{X : a(X)} #sum{X : b(X)} #count{X : b(X)}
                # self.language_bias_body.append(ModeDeclaration(("1",f"__{el}","1","positive"), False))
                md = ModeDeclaration(("1","","1","positive"), False)
                md.add_aggregate(el)
                self.language_bias_body.append(copy.deepcopy(md))
        
        # sys.exit()
        if self.args.arithmetic_operators:
            for el in self.args.arithmetic_operators:
                # self.body_literals.append(Literal(f"__{el}__",3,1,False))
                # self.language_bias_body.append(ModeDeclaration(("1",f"__{el}__","3","positive"), False))
                md = ModeDeclaration(("1",f"__{el}__","3","positive"), False)
                md.arithmetic_operator = el
                self.language_bias_body.append(copy.deepcopy(md))
        
        if self.args.comparison_operators:
            for el in self.args.comparison_operators:
                # self.body_literals.append(Literal(f"__{el}__",2,1,False))
                # self.language_bias_body.append(ModeDeclaration(("1",f"__{el}__","2","positive"), False))
                md = ModeDeclaration(("1",f"__{el}__","2","positive"), False)
                md.comparison_operator = el
                self.language_bias_body.append(copy.deepcopy(md))
                

    def __replace_operators(self, body : 'list[Literal]') -> 'list[list[str]]':
        '''
        Replaces the placeholder names with the comparison or arithmetic operator.
        '''
        body_literals : 'list[str]' = []
        aggregates_indexes : list[int] = []
        all_aggregates : 'list[list[str]]' = []
        placeholder = UNDERSCORE_SIZE*'_'
        operators_count = 0
        to_append : str = ""

        for i, el in enumerate(body):
            to_append = ""
            operators_count += 1
            # comparison
            if el.mode_bias.comparison_operator == "lt":
                to_append = placeholder + "<" + placeholder
            if el.mode_bias.comparison_operator == "leq":
                to_append = placeholder + "<=" + placeholder
            elif el.mode_bias.comparison_operator == "gt":
                to_append = placeholder + ">" + placeholder
            elif el.mode_bias.comparison_operator == "geq":
                to_append = placeholder + ">=" + placeholder
            elif el.mode_bias.comparison_operator == "eq":
                to_append = placeholder + "==" + placeholder
            elif el.mode_bias.comparison_operator == "neq":
                to_append = placeholder + "!=" + placeholder
            # arithmetic
            elif el.mode_bias.arithmetic_operator == "add":
                to_append = placeholder + "+" + placeholder + "=" + placeholder
            elif el.mode_bias.arithmetic_operator == "sub":
                to_append = placeholder + "-" + placeholder + "=" + placeholder
            elif el.mode_bias.arithmetic_operator == "mul":
                to_append = placeholder + "*" + placeholder + "=" + placeholder
            elif el.mode_bias.arithmetic_operator == "div":
                to_append = placeholder + "/" + placeholder + "=" + placeholder
            elif el.mode_bias.arithmetic_operator == "abs":
                to_append = "|" + placeholder + "-" + placeholder + "|=" + placeholder
            # aggregates
            elif el.mode_bias.aggregation_function != "":
                total_number_of_variables : int = sum([int(x[1]) for x in el.mode_bias.aggregation_atoms])
                if not self.args.unbalanced_aggregates:
                    # atoms_in_agg = ":"
                    atoms_in_agg : 'list[str]' = []
                    ph = ','.join([UNDERSCORE_SIZE*'_'] * total_number_of_variables)
                    for name, arity in el.mode_bias.aggregation_atoms:
                        ph_atom = ','.join([UNDERSCORE_SIZE*'_'] * int(arity))
                        atoms_in_agg.append(f"{name}({ph_atom})")
                    to_append = "#" + el.mode_bias.aggregation_function + "{" + ph + ":" + ','.join(atoms_in_agg) + "}=" + UNDERSCORE_SIZE*'_'
                else:
                    # if self.unbalanced_aggregates
                    # sum/2 -> #sum{ _ : a(_,_)} e #sum{ _, _ : a(_,_)}
                    current : 'list[str]' = []
                    for current_arity in range(1, total_number_of_variables + 1):
                        ph = ','.join([UNDERSCORE_SIZE*'_'] * int(current_arity))
                        atoms_in_agg : 'list[str]' = []
                        for name, arity in el.mode_bias.aggregation_atoms:
                            ph_atom = ','.join([UNDERSCORE_SIZE*'_'] * int(arity))
                            atoms_in_agg.append(f"{name}({ph_atom})")
                        s = "#" + el.mode_bias.aggregation_function + "{" + ph + ":" + ','.join(atoms_in_agg) + "}=" + UNDERSCORE_SIZE*'_'
                        current.append(s)
                    all_aggregates.append(current)
                    to_append = "__AGG_PLACEHOLDER__"

                operators_count -= 1
                aggregates_indexes.append(i)
            else:
                to_append = el.get_stub_representation()
                operators_count -= 1
            
            # append the literal to the body
            if to_append != "":
                body_literals.append(to_append)
        
        nb : 'list[list[str]]' = []
        for agg_comb in itertools.product(*all_aggregates):
            cb = body_literals[:]
            for agg, index in zip(agg_comb, aggregates_indexes):
                cb[index] = agg
            nb.append(cb)

        return nb

    
    def __sample_level_distr_recall(self, available_atoms : 'list[ModeDeclaration]', recalls : 'list[int]') -> 'Literal|None':
        '''
        Randomly samples an element if the recall is not 0
        '''
        weights = [1 if idx > 0 else 0 for idx in recalls]
        if not any(weights):
            # all zeros
            return None
        sampled_literal_pos = random.choices(range(len(available_atoms)), weights, k=1)[0]
        negated = random.random() < 0.5 and (not available_atoms[sampled_literal_pos].positive)

        return copy.deepcopy(Literal(copy.deepcopy(available_atoms[sampled_literal_pos]), negated, sampled_literal_pos))
    

    def __sample_literals_list(self,
            literals_list : 'list[ModeDeclaration]',
            head : bool = False
        ) -> 'list[Literal]':
        '''
        Samples a list of literals to be used in either in the head
        or in the body.
        head: True if the sampling is for the head of the rule (to allow constraints)
        body_constraint: True if the sampling is for a constraint (to 
            discard the possibility to sample constraints with a single
            atom, i.e., :- a(_).)
        '''
        # list_indexes_sampled_literals : 'list[Literal]' = [] # indexes
        sampled_list : 'list[Literal]' = []
        depth = 0
        stop = (random.random() > self.args.prob_increase) if head else False
        max_depth_head = self.args.disjunctive_head_length
        recalls : 'list[int]' = [x.recall for x in literals_list]

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
                    stop = (random.random() > self.args.prob_increase)
                depth += 1
            if head:
                max_depth_head -= 1
        return sampled_list

    
    def sample_clauses_stub(self, how_many : int = 0) -> 'list[Clause]':
        '''
        Samples how_many clauses.
        '''
        original_depth : int = self.args.max_depth
        # clauses : 'list[str]' = []
        clauses : 'list[Clause]' = []

        
        for _ in range(0, how_many):
            body : 'list[Literal]' = []
            head : 'list[Literal]' = []
            
            if len(self.language_bias_head) > 0:
                head = self.__sample_literals_list(self.language_bias_head, True) # true allows constraints
                self.body_constraint = (len(head) == 0)
        
            # decrease the depth since we already sampled atoms for the head
            self.args.max_depth -= len(head)
            
            # print(self.body_literals)
            body = self.__sample_literals_list(self.language_bias_body)

            # replace __lt__, __gt__, __eq__, __neq__, __add__, __sub__, __mul__
            body_list = self.__replace_operators(body)
            
            if self.enable_recursion:
                print_error_and_exit("self.enable_recursion not yet implemented.")

            current_clause : 'Clause' = Clause(head, body, [])
            for b in body_list:
                subs_h = set(head).issubset(set(b)) and len(set(head)) > 0
                subs_b = set(b).issubset(set(head)) and len(set(b)) > 0
                is_valid = not (subs_h or subs_b)
                if is_valid:
                    head_as_str : str = ';'.join(sorted([x.get_stub_representation() for x in head]))
                    body_as_str : str = ','.join(sorted(b))
                    cl = f"{head_as_str} :- {body_as_str}."
                    current_clause.instantiated.append(cl)

            if current_clause not in clauses:
                # avoid duplicates
                clauses.append(copy.deepcopy(current_clause))

            self.args.max_depth = original_depth

        return clauses
    
