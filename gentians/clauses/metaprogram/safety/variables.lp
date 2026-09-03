% Variable usage and canonical names.
%
% This file enforces that generated variables are meaningful and canonically
% numbered. Singleton variables are allowed only as existential projections in
% positive normal body literals or as aggregate locals; variable ids must be
% dense from 0; and first occurrences must appear in id order.
%
% Shared atom shapes used here:
% - var_at(Section,Slot,Arg,Var): concrete variable assignment.
% - var(Var): allowed variable id from core/slots.lp.
% - normal_positive_body_var(Var): positive normal body safety alias.
% - aggregate_condition_var(Slot,Var), aggregate_tuple_var(Slot,Var),
%   aggregate_result_var(Slot,Var): aggregate role predicates from
%   aggregates/roles.lp.

% Rule: mark every generated variable that appears in any selected argument.
% Var is used if any var_at(_,_,_,Var) exists.
used_var(Var):- var_at(_,_,_,Var).

% Rule: mark variables that occur at least twice.
% S0/L0/A0 and S1/L1/A1 are two ordered positions containing the same Var.
% The tuple comparison avoids deriving the same repeated_var fact twice from
% reversed positions.
repeated_var(Var):-
    var_at(S0,L0,A0,Var),
    var_at(S1,L1,A1,Var),
    (S0,L0,A0) < (S1,L1,A1).

% Rule: mark aggregate-local variables allowed to appear once globally.
% Slot is an aggregate body slot. Var occurs in the aggregate condition part,
% is not a grouped tuple variable, and is not the aggregate result variable.
% Such variables can be local to the aggregate element condition.
aggregate_local_var(Slot,Var):-
    aggregate_condition_var(Slot,Var),
    not aggregate_tuple_var(Slot,Var),
    not aggregate_result_var(Slot,Var).

% Constraint: reject singleton variables unless they are safe existentials.
% A one-off variable in a positive normal body literal is an ASP-safe
% existential projection. Aggregate condition locals are also safe. Every
% other singleton remains rejected.
:- used_var(Var),
    not repeated_var(Var),
    not normal_positive_body_var(Var),
    not aggregate_local_var(_,Var),
    not conditional_local_var(_,_,Var).

% Constraint: reject gaps in variable ids.
% If Var1 is used and a smaller Var0 exists, Var0 must also be used. This keeps
% equivalent clauses using V1,V2 instead of V0,V1 out of the model space.
:- used_var(Var1), var(Var0), Var0 < Var1, not used_var(Var0).

% Rule: compute first occurrence position for each variable.
% Var is a used variable. Section/Slot/Arg is the minimum tuple among all
% positions containing Var. #min uses clingo tuple ordering.
first_var_pos(Var,Section,Slot,Arg):-
    used_var(Var),
    (Section,Slot,Arg) = #min{(S,L,A) : var_at(S,L,A,Var)}.

% Constraint: variable ids must follow first-use order.
% Var0 < Var1 means Var0 should appear no later than Var1. If Var0's first
% position is greater than Var1's first position, the same clause can be encoded
% by renaming variables, so this encoding is rejected.
:- first_var_pos(Var0,S0,L0,A0),
    first_var_pos(Var1,S1,L1,A1),
    Var0 < Var1,
    (S0,L0,A0) > (S1,L1,A1).

