% Choose dense variable ids ordered by their first occurrence.
% These comparisons order syntactic ids, not their object-level values.

:- used_var(Var1), var(Var0), Var0 < Var1, not used_var(Var0).

first_var_pos(Var, Section, Slot, Arg) :-
    used_var(Var),
    (Section, Slot, Arg) = #min{(S, L, A) : var_at(S, L, A, Var)}.

:- first_var_pos(Var0, S0, L0, A0),
    first_var_pos(Var1, S1, L1, A1),
    Var0 < Var1,
    (S0, L0, A0) > (S1, L1, A1).
