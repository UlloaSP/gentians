% Declared types are nominal and must agree inside each variable scope.
% Independent local aggregate/conditional scopes may reuse a variable name
% with different types; a global occurrence connects those positions.
%
% Two occurrences of one variable id denote the same variable unless both are
% local to different constructs. That gives two checks: inside one literal,
% and between a non-local occurrence and every other occurrence. They are
% stated per variable rather than per pair of placeholders, which would
% ground every pair of positions of the clause.

% DEFINITION, local helper. separate_aggregate_local_elements(body, Slot, A0,
% A1): two placeholders of one body aggregate are local to different elements.
%   body    the section; aggregates handled here occur only in the body.
%   Slot    body slot of the aggregate.
%   A0, A1  local placeholder positions owned by two different elements.
% In "#count{V0 : p(V0) ; V0 : q(V0)}" the two V0 are different variables.
% Used only, negated, by the constraint below.
separate_aggregate_local_elements(body, Slot, A0, A1) :-
    aggregate_element_arg(Slot, E0, A0), aggregate_element_arg(Slot, E1, A1),
    E0 != E1, local_var_at(body, Slot, A0), local_var_at(body, Slot, A1).

% CONSTRAINT. Inside one literal, a variable may not sit at two placeholders
% of different declared types, unless the two are local to different elements
% of one aggregate.
%   Section, Slot  the literal.
%   A0 < A1        two of its placeholders holding the same variable Var.
%   Type0, Type1   their declared types.
% A placeholder declared "any" has no type and never conflicts. With
% #modeb(1,lives(var(person,any),var(city,any))):
%   pruned: :- lives(V0,V0).
%   kept:   :- lives(V0,V1).
%   kept:   :- #count{V0 : person(V0) ; V0 : city(V0)} = V1, n(V1).
%           each V0 is local to its own element
:- var_at(Section, Slot, A0, Var),
    var_at(Section, Slot, A1, Var),
    A0 < A1,
    not separate_aggregate_local_elements(Section, Slot, A0, A1),
    arg_type(Section, Slot, A0, Type0),
    arg_type(Section, Slot, A1, Type1),
    Type0 != Type1.

% DEFINITION, local helper. variable_type(Var, Type): some placeholder holding
% Var declares Type.
%   Var   variable id.
%   Type  nominal type declared at any of its occurrences, local or not.
% Used only by the last constraint.
variable_type(Var, Type) :-
    var_at(Section, Slot, Arg, Var),
    arg_type(Section, Slot, Arg, Type).

% DEFINITION, local helper. global_variable_type(Var, Type): a non-local
% placeholder holding Var declares Type.
%   Var   variable id with an occurrence outside local constructs.
%   Type  nominal type declared at such an occurrence.
% A non-local occurrence is the same variable as every other occurrence of
% the name, in any literal. Used only by the last constraint.
global_variable_type(Var, Type) :-
    var_at(Section, Slot, Arg, Var),
    not local_var_at(Section, Slot, Arg),
    arg_type(Section, Slot, Arg, Type).

% CONSTRAINT. A variable with a non-local occurrence may not sit anywhere at
% a placeholder of a different declared type.
%   Var    the variable id.
%   Type0  a type declared at one of its non-local occurrences.
%   Type1  a different type declared at any of its occurrences.
% With #modeb(1,person(var(person,any))) and #modeb(1,city(var(city,any))):
%   pruned: :- person(V0), city(V0).      V0 would be both person and city
%   kept:   :- person(V0), city(V1).
%   kept:   :- #count{V0 : person(V0)} = V1, #count{V0 : city(V0)} = V1.
%           each V0 is local to its own aggregate, so the types do not meet
:- global_variable_type(Var, Type0),
    variable_type(Var, Type1),
    Type0 != Type1.
