% Duplicate aggregate computation pruning.
%
% This file rejects pairs of selected aggregate literals that compute the same
% aggregate inputs with the same mode but bind different result variables.
%
% Shared atom shapes used here:
% - aggregate_mode(Mode,TupleArity,AtomCount): Python fact for aggregate modes.
% - selected(body,Slot,Mode): selected body aggregate literal.
% - aggregate_internal_arg(Slot,Arg): tuple/condition argument positions,
%   excluding result.
% - aggregate_result_var(Slot,Var): result variable of aggregate Slot.
% - var_at(body,Slot,Arg,Var): concrete aggregate argument assignment.

% Python fact contract:
% - aggregate_mode(Mode,TupleArity,AtomCount): emitted by Python for aggregate
%   modes. This file needs only Mode identity to compare same aggregate kind.
% Python fact detail: aggregate_mode(Mode,TupleArity,AtomCount) marks aggregate modes; TupleArity is grouped tuple length, AtomCount is condition atom count.
#defined aggregate_mode/3.

% Rule: two same-mode aggregate slots differ in at least one input argument.
% Slot0 and Slot1 use the same aggregate Mode. Arg is an internal aggregate
% argument position. Left and Right are variables at that position. If they
% differ, the two aggregates compute different grouped/condition inputs.
aggregate_input_differs(Slot0,Slot1):-
    selected(body,Slot0,Mode),
    selected(body,Slot1,Mode),
    aggregate_mode(Mode,_,_),
    aggregate_internal_arg(Slot0,Arg),
    var_at(body,Slot0,Arg,Left),
    var_at(body,Slot1,Arg,Right),
    Left != Right.

% Rule: two aggregate slots have identical inputs.
% Slot0 < Slot1 orders the pair. Both slots use the same aggregate Mode. If no
% aggregate_input_differs fact exists, every internal argument matches.
same_aggregate_inputs(Slot0,Slot1):-
    selected(body,Slot0,Mode),
    selected(body,Slot1,Mode),
    aggregate_mode(Mode,_,_),
    Slot0 < Slot1,
    not aggregate_input_differs(Slot0,Slot1).

% Constraint: identical aggregate computations must bind the same result.
% Result0 and Result1 are result variables of the two same-input aggregates.
% Different result variables would create duplicate definitions of one value.
:- same_aggregate_inputs(Slot0,Slot1),
    aggregate_result_var(Slot0,Result0),
    aggregate_result_var(Slot1,Result1),
    Result0 != Result1.
