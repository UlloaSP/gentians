% Declared types are nominal and must agree inside each variable scope.
% Independent local aggregate/conditional scopes may reuse a variable name
% with different types; a global occurrence connects those positions.

same_variable_scope(Section, Slot, A0, Section, Slot, A1, Var) :-
    var_at(Section, Slot, A0, Var),
    var_at(Section, Slot, A1, Var).

same_variable_scope(S0, L0, A0, S1, L1, A1, Var) :-
    var_at(S0, L0, A0, Var),
    var_at(S1, L1, A1, Var),
    not local_var_at(S0, L0, A0).

same_variable_scope(S0, L0, A0, S1, L1, A1, Var) :-
    var_at(S0, L0, A0, Var),
    var_at(S1, L1, A1, Var),
    not local_var_at(S1, L1, A1).

:- same_variable_scope(Section0, Slot0, Arg0, Section1, Slot1, Arg1, Var),
    arg_type(Section0, Slot0, Arg0, Type0),
    arg_type(Section1, Slot1, Arg1, Type1),
    Type0 != Type1.
