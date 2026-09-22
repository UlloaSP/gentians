% Variable occurrence and repeated-name relations; ids denote syntax, not values.

used_var(Var) :- var_at(_, _, _, Var).

repeated_var(Var) :-
    var_at(S0, L0, A0, Var),
    var_at(S1, L1, A1, Var),
    (S0, L0, A0) < (S1, L1, A1).

aggregate_local_var(Slot, Var) :-
    aggregate_condition_var(Slot, Var),
    not aggregate_tuple_var(Slot, Var),
    not aggregate_result_var(Slot, Var).
