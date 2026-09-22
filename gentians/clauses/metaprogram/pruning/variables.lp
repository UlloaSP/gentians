% Prune singleton variables and choose dense ids in first-occurrence order.
% Singletons are retained when they are safe existential projections in positive
% body atoms or local aggregate/conditional variables. Renaming removes the
% remaining alternative encodings without changing the rendered rule.

used_var(Var):- var_at(_,_,_,Var).

repeated_var(Var):-
    var_at(S0,L0,A0,Var),
    var_at(S1,L1,A1,Var),
    (S0,L0,A0) < (S1,L1,A1).

aggregate_local_var(Slot,Var):-
    aggregate_condition_var(Slot,Var),
    not aggregate_tuple_var(Slot,Var),
    not aggregate_result_var(Slot,Var).

:- used_var(Var),
    not repeated_var(Var),
    not normal_positive_body_var(Var),
    not aggregate_local_var(_,Var),
    not conditional_local_var(_,_,Var).

:- used_var(Var1), var(Var0), Var0 < Var1, not used_var(Var0).

first_var_pos(Var,Section,Slot,Arg):-
    used_var(Var),
    (Section,Slot,Arg) = #min{(S,L,A) : var_at(S,L,A,Var)}.

:- first_var_pos(Var0,S0,L0,A0),
    first_var_pos(Var1,S1,L1,A1),
    Var0 < Var1,
    (S0,L0,A0) > (S1,L1,A1).
