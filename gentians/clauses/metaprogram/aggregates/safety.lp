% Aggregate safety and variable placement.
%
% This file enforces ASP-safe aggregate usage for generated aggregate literals.
% It makes aggregate results useful, keeps tuple variables local to the
% aggregate literal, and prevents aggregate-internal variables from leaking
% unless they are supported by a positive normal body literal.
%
% Shared atom shapes used here:
% - aggregate_result_var(Slot,Var): result variable of aggregate Slot.
% - aggregate_tuple_var(Slot,Var): grouped tuple variable of aggregate Slot.
% - aggregate_condition_var(Slot,Var): condition-side variable of aggregate Slot.
% - aggregate_internal_arg(Slot,Arg): tuple/condition arg index inside Slot.
% - var_used_outside_body_slot(Slot,Var): safety/asp_safety.lp helper.
% - normal_positive_body_var(Var): safety/asp_safety.lp helper.
% - var_at(Section,Slot,Arg,Var): concrete variable assignment.

% Constraint: aggregate result must be consumed outside the aggregate slot.
% Slot is aggregate body slot. Var is the result variable. If Var is not used
% in another body slot or head slot, the aggregate literal has no effect.
:- aggregate_result_var(Slot,Var),
    not var_used_outside_body_slot(Slot,Var).

% Constraint: every aggregate tuple variable must occur in the condition.
% Tuple variables before the colon must be bound by condition atoms after the
% colon. Slot identifies the aggregate literal; Var is the tuple variable.
:- aggregate_tuple_var(Slot,Var), not aggregate_condition_var(Slot,Var).

% Constraint: leaking condition-local variables need positive-body support.
% Var is a condition variable that is not part of the aggregate tuple. If Var
% appears outside Slot, it must also occur in a positive normal body literal.
:- aggregate_condition_var(Slot,Var),
    not aggregate_tuple_var(Slot,Var),
    var_used_outside_body_slot(Slot,Var),
    not normal_positive_body_var(Var).

% Constraint: aggregate condition variables cannot be aggregate results unless
% supported by a positive normal body literal.
% This avoids circular binding between condition internals and result variables.
:- aggregate_condition_var(_,Var), aggregate_result_var(_,Var), not normal_positive_body_var(Var).

% Constraint: aggregate tuple variables may not appear in the head.
% Tuple variables are scoped to aggregate grouping and condition. Using them in
% the head would leak aggregate-local structure into the rule head.
:- aggregate_tuple_var(Slot,Var),
    var_at(head,_,_,Var).

% Constraint: aggregate tuple variables may not appear in another body slot.
% Slot is the owning aggregate. OtherSlot is any different body slot. Tuple Var
% must stay internal to its aggregate literal.
:- aggregate_tuple_var(Slot,Var),
    var_at(body,OtherSlot,_,Var),
    OtherSlot != Slot.

% Constraint: aggregate tuple variables may appear only in aggregate internals.
% Arg is a position in the same Slot using tuple Var. aggregate_internal_arg
% allows tuple and condition positions, but excludes the result position.
:- aggregate_tuple_var(Slot,Var),
    var_at(body,Slot,Arg,Var),
    not aggregate_internal_arg(Slot,Arg).
