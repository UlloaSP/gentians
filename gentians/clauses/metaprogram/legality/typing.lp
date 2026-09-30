% Declared types are nominal and must agree inside each variable scope.
% Independent local aggregate/conditional scopes may reuse a variable name
% with different types; a global occurrence connects those positions.

% DEFINITION, local helper. same_variable_scope(S0, L0, A0, S1, L1, A1, Var):
% two placeholders hold the same name AND denote the same variable.
%   S0, L0, A0  section, slot and placeholder position of the first occurrence.
%   S1, L1, A1  section, slot and placeholder position of the second.
%   Var         the variable id written at both.
% Two occurrences of one id are one variable unless both are local to
% different constructs. Used only by the constraint below.
% Case 1: both placeholders belong to the same literal, except when they are
% local placeholders of two different elements of one aggregate.
same_variable_scope(Section, Slot, A0, Section, Slot, A1, Var) :-
    var_at(Section, Slot, A0, Var),
    var_at(Section, Slot, A1, Var),
    not separate_aggregate_local_elements(Section, Slot, A0, A1).

% DEFINITION, local helper. separate_aggregate_local_elements(body, Slot, A0,
% A1): two placeholders of one body aggregate are local to different elements.
%   body    the section; aggregates handled here occur only in the body.
%   Slot    body slot of the aggregate.
%   A0, A1  local placeholder positions owned by two different elements.
% In "#count{V0 : p(V0) ; V0 : q(V0)}" the two V0 are different variables.
% Used only, negated, by the rule above.
separate_aggregate_local_elements(body, Slot, A0, A1) :-
    aggregate_element_arg(Slot, E0, A0), aggregate_element_arg(Slot, E1, A1),
    E0 != E1, local_var_at(body, Slot, A0), local_var_at(body, Slot, A1).

% DEFINITION, local helper. same_variable_scope, case 2: the first placeholder
% is not local. A global occurrence is the same variable as every other
% occurrence of the name, in any literal.
same_variable_scope(S0, L0, A0, S1, L1, A1, Var) :-
    var_at(S0, L0, A0, Var),
    var_at(S1, L1, A1, Var),
    not local_var_at(S0, L0, A0).

% DEFINITION, local helper. same_variable_scope, case 3: the second
% placeholder is not local.
same_variable_scope(S0, L0, A0, S1, L1, A1, Var) :-
    var_at(S0, L0, A0, Var),
    var_at(S1, L1, A1, Var),
    not local_var_at(S1, L1, A1).

% CONSTRAINT. One variable may not sit at placeholders of different declared
% types.
%   Section0, Slot0, Arg0, Type0  one occurrence and its declared type.
%   Section1, Slot1, Arg1, Type1  another occurrence of the same variable and
%                                 its declared type.
% A placeholder declared "any" has no type and never conflicts. With
% #modeb(1,person(var(person,any))) and #modeb(1,city(var(city,any))):
%   pruned: :- person(V0), city(V0).      V0 would be both person and city
%   kept:   :- person(V0), city(V1).
%   kept:   :- #count{V0 : person(V0)} = V1, #count{V0 : city(V0)} = V1.
%           each V0 is local to its own aggregate, so the types do not meet
:- same_variable_scope(Section0, Slot0, Arg0, Section1, Slot1, Arg1, Var),
    arg_type(Section0, Slot0, Arg0, Type0),
    arg_type(Section1, Slot1, Arg1, Type1),
    Type0 != Type1.
