import re
import itertools
from importlib import resources

from .utils import UNDERSCORE_SIZE
from .utils import AggregateElement
from .utils import is_valid_rule
from .utils import from_list_to_as, from_as_to_list
from .utils import get_arithmetic_or_comparison_position, get_aggregates, get_same_atoms
from .utils import contains_comparison, contains_arithmetic

from .clingo_interface import ClingoInterface
from .arguments import Arguments



class VariablePlacer:
    def __init__(self, args : Arguments) -> None:
        def get_content(filename : str) -> str:
            return resources.files("gentians").joinpath(filename).read_text()

        self.args : Arguments = args
        # dict: hash of the asp program to place vars -> result, to avoid the
        # same computation
        self.already_encountered_asp_programs : 'dict[int,list[list[list[int]]]]' = {}

        self.base_rules = get_content("logic_programs/base_rules.lp")
        self.equal_rules = get_content("logic_programs/equal_rules.lp")
        self.rules_for_aggregates_arithm_comparison = get_content("logic_programs/rules_for_aggregates_arithm_comparison.lp")
        self.rules_for_aggregates = get_content("logic_programs/rules_for_aggregates.lp")
        self.rules_for_arithm = get_content("logic_programs/rules_for_arithm.lp")
        self.rules_for_comparison = get_content("logic_programs/rules_for_comparison.lp")
        self.rules_only_standard_atoms = get_content("logic_programs/rules_only_standard_atoms.lp")

    
    def __reconstruct_clause(self, model : str, rule_stub : str) -> str:
        atoms = model.split(' ')

        # print(f'IN: {rule_stub}')
        r = rule_stub
        for el in atoms:
            position = int(el.split('(')[1][:-1])
            var = int(el.split('(')[0][1:])
            r = r.replace(f'_v{position:02d}_',f"V{var}")

        # print(f'OUT: {r}')
        return r


    def __generate_asp_program_for_combinations(
        self,
        n_positions : int,
        n_variables : int,
        n_vars_in_head : int,
        to_find_max_number : bool = False,
        aggregates : 'list[AggregateElement]' = [],
        pos_arithm : 'list[list[int]]' = [],
        pos_comparison : 'list[list[int]]' = [],
        same_atoms : 'list[str]' = [],
        arity_same_atoms : int = 0
        ) -> str:
        '''
        Generate an answer set program to fill the holes in rules.
        to_find_max_number adds some rules to maximize the number
        of clauses. In this way we find the maximum number according
        to the constraints and avoid the generation of unused rules 
        to compute the possible choices.
        TODO: improve the unsafety check (not trivial)
        '''

        s : str = ""
        s += "% generate all the combinations of variables and positions\n"
        s += f"var(0..{n_variables - 1}).\n"
        s += f"pos(0..{n_positions - 1}).\n"
        s += "% last index for the variable in the head\n"
        s += f"last_index_var_in_head({n_vars_in_head - 1}).\n"

        s += self.base_rules
        s += self.equal_rules

        if len(aggregates) > 0 or len(pos_comparison) > 0 or len(pos_arithm) > 0:
            s += self.rules_for_aggregates_arithm_comparison
        else:
            s += self.rules_only_standard_atoms
        
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
            s += self.rules_for_aggregates
            s += "\n% constraints for aggregates\n"
            s += f"aggregate(0..{len(aggregates) - 1}).\n"
            for index, aggregate in enumerate(aggregates):
                last_i = -1
                for t in aggregate.position_var_terms:
                    s += f"aggregate_term_position({index},{t}).\n"
                for a in aggregate.position_var_atom:
                    s += f"aggregate_atom_position({index},{a}).\n"
                    last_i = aggregate.position_var_atom[len(aggregate.position_var_atom) - 1]
                s += f"aggregate_result_position({index},{last_i + 1}).\n"
        
            if not self.args.unbalanced_aggregates:
                s += "\n% no global variables in tuple of aggregate elements\n"
                s += "not_agg_pos(P):- pos(P), not aggregate_term_position(_,P), not aggregate_atom_position(_,P).\n"
                s += ":- not_agg_pos(P), var_pos(V,P), aggregate_term_position(_,PosTermAgg), var_pos(V,PosTermAgg).\n"

        if len(pos_arithm) > 0:
            # the variables involved in arithmetic operators must be already defined
            # in another term
            s += self.rules_for_arithm
            s += "\n% constraints for arithm operators\n"
            s += f"arithm(0..{len(pos_arithm) - 1}).\n"
            for index, el in enumerate(pos_arithm):
                for ii in range(0,len(el)):
                    # if index > 0 and (index + 1) % 3 != 0:
                    if (ii + 1) % 3 != 0:
                        # since in A + B = C, C can appear in the head
                        s += f"arithm_term_position({index},{el[ii]}).\n"
                    else:
                        s += f"result_term_position({index},{el[ii]}).\n"
                    s += f"all_arithm_term_position({index},{el[ii]}).\n"

        if len(pos_comparison) > 0:
            s += self.rules_for_comparison
            s += "\n% constraints for comparison operators\n"
            s += f"comparison(0..{len(pos_comparison) - 1}).\n"
            for index, el in enumerate(pos_comparison):
                for v in el:
                    s += f"comparison_term_position({index},{v}).\n"
        
        for v in same_atoms:
            s += v + '\n'

        return s


    def _place_variables_clause(self, sampled_stub : str) -> 'list[str]':
        '''
        Replaces the _____ with the variables in the clause.
        This now works with only 1 clause
        '''
        # print("-- FIXED STUB ")
        # sampled_stub = ":- a(_____,_____),a(_____,_____)."
        # sampled_stub = "d(V0,V0):- #sum{V1,V2:d(V2,V1)}=V0."
        # sampled_stub = " :- x(_____,_____,_____), x(_____,_____,_____), less_than(_____,_____, _____,_____), _____ >= _____."
        # sampled_stub = ":- #sum{_____:x(_____),size(_____)}=_____,_____!=_____,size(_____),sum_col(_____,_____)."
        # sampled_stub = "sum_partition(_____,_____):- #sum{_____:p(_____,_____)}=_____,partition(_____)."
        # sampled_stub = ":- #sum{_____:p(_____,_____)}=_____, #sum{_____:p(_____,_____)}=_____."
        # sampled_stub = ":- #sum{_____:p(_____,_____)}=_____."
        # sampled_stub = ":- _____+_____=_____,_____-_____=_____,_____<_____,_____==_____,q(_____,_____)."
        # sampled_stub = ":- _____+_____=_____,_____>_____,q(_____,_____)." # qui attenzione che se ho > o < invece di == allora è unsafe
        # sampled_stub = ":- _____+_____=_____,q(_____,_____)."
        # sampled_stub = ":- q(_____,_____,_____),q(_____,_____,_____)."
        # sampled_stub = ":- #sum{_____,_____:el(_____,_____)}=_____,#sum{_____,_____:el(_____,_____)}=_____,_____+_____=_____,s1(_____)."
        # sampled_stub = ":- _____==_____,q(_____,_____)."
        # sampled_stub = ":- _____-_____=_____,_____<_____."
        # sampled_stub = ":- _____>_____,q(_____,_____)."
        # sampled_stub = ":- q(_____,_____),q(_____,_____),a(_____),a(_____)."
        # sampled_stub = "sp(_____,_____):- #sum{_____,_____:p(_____,_____)}=_____, partition(_____)."
        # sampled_stub = ":- _____-_____=_____,_____<=_____,hd(_____),pos(_____),sd(_____),v1(_____,_____)."
        # sampled_stub = ":- #sum{_____,_____:d(_____,_____)}=_____,_____-_____=_____,_____>=_____."
        # sampled_stub = "s0(_____):- #sum{_____,_____:el(_____,_____)}=_____,#sum{_____,_____:el(_____,_____)}=_____."
        # sampled_stub = "s1(_____):- #sum{_____,_____:el(_____,_____)}=_____,#sum{_____,_____:el(_____,_____)}=_____,s1(_____)."
        # sampled_stub = "odd(_____):- even(_____), prev(_____,_____)."
        
        # sampled_stub = "a(_____):- _____ + _____ = _____, b(_____), c(_____)."
        # sampled_stub = ":- #sum{ _____,_____ : el  ( _____,_____ )} = _____,#sum{ _____,_____ : el  ( _____,_____ )} = _____,s0(_____),s1(_____)."
        
        # sampled_stub = "s(_____,_____):- g(_____), h(_____,_____), i(_____)."
        # sampled_stub = "ok(_____):- #sum{ _____,_____ : el  ( _____,_____ )} = _____,#sum{ _____,_____ : el  ( _____,_____ )} = _____,_____ + _____ = _____."
        # sampled_stub = ":- s(_____), s(_____), s(_____), _____ + _____ = _____."
        # sampled_stub = "s(_____):- #sum{ _____ : el  ( _____ )} = _____, _____ != _____."
        # sampled_stub = ":- #sum{ _____ : el  ( _____ )} = _____,_____ != _____,s(_____)."
        # sampled_stub = "g(_____):- #sum{ _____, _____ : a  ( _____, _____ )} = _____."
        # sampled_stub = "g(_____):- #sum{ _____ : a  ( _____ )} = _____, #sum{ _____ : a  ( _____ )} = _____."
        # sampled_stub = "g(_____):- #sum{ _____ : a  ( _____ )} = _____."
        # sampled_stub = "count_row(_____,_____):- _____ = #count{_____ : x(_____,_____,_____), cell(_____)}, cell(_____)."
        # sampled_stub = ":- in(_____), in(_____), v(_____), v(_____), _____!=_____, not e(_____,_____), not e(_____,_____)."
        
        res : 'list[str]' = []
        # number of positions to insert the variables
        n_positions : int = sampled_stub.count('_' * UNDERSCORE_SIZE)
        rv = self.args.max_variables # deterministic is better
        if n_positions <= 2:
            n_variables = 1
        else:
            n_variables = rv
        
        if self.args.verbosity > 1:
            print(f"Placing for the stub: {sampled_stub}")
        
        n_vars_in_head = sampled_stub.split(':-')[0].count('_' * UNDERSCORE_SIZE)

        aggregates : 'list[AggregateElement]' = []
        pos_arithm : 'list[list[int]]' = []
        pos_comparison : 'list[list[int]]' = []

        if '#' in sampled_stub:
            aggregates = get_aggregates(sampled_stub)

        if contains_arithmetic(sampled_stub) or contains_comparison(sampled_stub):
            pos_arithm, pos_comparison = get_arithmetic_or_comparison_position(sampled_stub)

        # Possible: improvements
        # 1) la variabile coinvolta in una ricorsione deve variare
        # es: a(X):- b(X), a(X).
        # 2) no variabili unsafe (quando c'è negazione)   

        same_atoms, arity_same = get_same_atoms(sampled_stub)
        
        asp_p = self.__generate_asp_program_for_combinations(
            n_positions,
            n_variables,
            n_vars_in_head,
            False,
            aggregates,
            pos_arithm=pos_arithm,
            pos_comparison=pos_comparison,
            same_atoms=same_atoms,
            arity_same_atoms=arity_same           
        )

        # generates the clause to fill
        for el in range(0, sampled_stub.count('_'*UNDERSCORE_SIZE)):
            sampled_stub = re.sub('_'*UNDERSCORE_SIZE, f"_v{el:02d}_", sampled_stub, count=1)

        if hash(asp_p) in self.already_encountered_asp_programs:
            # already placed variables in an equivalent program,
            # retrieve it: I cannot store the clauses since the stub
            # is different, I need to reconstruct again the clause
            r = self.already_encountered_asp_programs[hash(asp_p)]
        else:
            asp_interface = ClingoInterface([asp_p], ["0"])
            ctl = asp_interface.init_clingo_ctl()      

            # answer_sets : 'list[str]' = []
            answer_sets_in_list : 'list[list[list[int]]]' = []
            if self.args.verbosity > 1:
                print("Generating variables placements")
            with ctl.solve(yield_=True) as handle:  # type: ignore
                for m in handle:  # type: ignore
                    # print(str(m))
                    a = str(m).split(' ')
                    a.sort()
                    a = ' '.join(a)
                    # answer_sets.append(a)
                    answer_sets_in_list.append(from_as_to_list(str(a)))
                    # res.append(self.__reconstruct_clause(str(m), sampled_stub))
            if self.args.verbosity > 1:
                print("Removing symmetries")

            answer_sets_in_list.sort()
            # remove duplicates
            r = list(k for k,_ in itertools.groupby(answer_sets_in_list))
            self.already_encountered_asp_programs[hash(asp_p)] = r
        
        # reconstruct the clause
        for rt in r:
            res.append(self.__reconstruct_clause(from_list_to_as(rt), sampled_stub))

        return res
    
    
    def place_variables_list_of_clauses(self, sampled_clauses : 'list[str]') -> 'list[list[str]]':
        '''
        Loop to place the variable in all the sampled clauses
        '''
        placed_list : 'list[list[str]]' = []
        
        for index, clause in enumerate(sampled_clauses):
            if self.args.verbosity >= 1:
                print(f"({index}/{len(sampled_clauses) - 1}) Placing variables for {clause}")

            r = self._place_variables_clause(clause)

            if len(r) > 0:
                r.sort()
                valid_rules : 'list[str]' = []
                pruned_count = 0
                for rl in r:
                    if is_valid_rule(rl):
                        valid_rules.append(rl)
                        if self.args.verbosity > 1:
                            print(f"Valid: {rl}")
                    else:
                        pruned_count += 1
                        if self.args.verbosity > 1:
                            print(f"Pruned: {rl}")
                if self.args.verbosity > 1:
                    print(f"Valid / Total = {len(r) - pruned_count} / {len(r)} = {(len(r) - pruned_count) / len(r)}")
                if len(valid_rules) > 0:
                    placed_list.append(valid_rules)
                if self.args.verbosity == 1:
                    print(f"Generated {len(valid_rules)} clauses")
            else:
                if self.args.verbosity >= 1:
                    print("No possible placements.")

        return placed_list
