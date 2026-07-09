% Aggregate canonicalization.
%
% This file removes aggregate encodings that are invalid or redundant:
% duplicated tuple variables, descending count tuple variables, and duplicated
% condition variables inside one aggregate condition.
%
% Shared atom shapes used here:
% - aggregate_mode(Mode,TupleArity,AtomCount): Python fact for aggregate modes.
% - aggregate_has_shorter_mode(Mode): same aggregate exists with one fewer
%   tuple argument.
% - count_aggregate_mode(Mode): Python fact for count aggregates.
% - sum_aggregate_mode(Mode): Python fact for sum aggregates.
% - key_pred(Pred,Key), key_arg(Key,Arg): property facts for condition preds.
% - selected(body,Slot,Mode): selected body aggregate.
% - mode(body,Mode,Pred,Arity,Recall): flattened arity for aggregate Mode.
% - var_at(body,Slot,Arg,Var): variable assignment.

% Python fact contract:
% - aggregate_mode(Mode,TupleArity,AtomCount): emitted by Python for aggregate
%   modes. TupleArity splits tuple args from condition args.
% - aggregate_has_shorter_mode(Mode): emitted by Python when dropping one
%   redundant tuple argument is representable by another aggregate mode.
% - count_aggregate_mode(Mode): emitted by Python when Mode renders as #count.
% - sum_aggregate_mode(Mode): emitted by Python when Mode renders as #sum.
% - key_pred(Pred,Key), key_arg(Key,Arg): emitted by Python/property rules when
%   aggregate condition predicate args contain a key.
% Python fact detail: aggregate_mode(Mode,TupleArity,AtomCount) marks aggregate modes; TupleArity is grouped tuple length, AtomCount is condition atom count.
#defined aggregate_mode/3.
% Python fact detail: aggregate_has_shorter_mode(Mode) marks aggregate modes with an equivalent shorter tuple shape available when a discriminator is key-determined.
#defined aggregate_has_shorter_mode/1.
% Python fact detail: count_aggregate_mode(Mode) marks aggregate modes rendered as #count.
#defined count_aggregate_mode/1.
% Python fact detail: sum_aggregate_mode(Mode) marks aggregate modes rendered as #sum.
#defined sum_aggregate_mode/1.
% Python fact detail: key_pred(Pred,Key) assigns key id Key to predicate id Pred.
#defined key_pred/2.
% Python fact detail: key_arg(Key,Arg) lists one zero-based arg in Key.
#defined key_arg/2.

% Constraint: tuple/grouping variables inside one aggregate must be distinct.
% Slot is aggregate slot. A0 and A1 are two tuple argument positions before the
% condition arguments. If both positions use the same Var, the aggregate tuple
% has duplicate entries and can be represented with fewer tuple variables.
:- selected(body,Slot,Mode),
    aggregate_mode(Mode,TupleArity,_),
    A0 = 0..TupleArity-1,
    A1 = 0..TupleArity-1,
    A0 < A1,
    var_at(body,Slot,A0,Var),
    var_at(body,Slot,A1,Var).

% Constraint: count aggregate tuple variables are ordered canonically.
% A0/A1 are tuple argument positions with A0 < A1. Left/Right are their
% variable ids. For #count, tuple variable order does not change count meaning,
% so descending variable ids are rejected.
:- selected(body,Slot,Mode),
    count_aggregate_mode(Mode),
    aggregate_mode(Mode,TupleArity,_),
    A0 = 0..TupleArity-1,
    A1 = 0..TupleArity-1,
    A0 < A1,
    var_at(body,Slot,A0,Left),
    var_at(body,Slot,A1,Right),
    Left > Right.

% Rule: a full-local count aggregate condition has exactly one condition atom,
% all condition args are the local tuple vars, and none of those vars escapes
% this aggregate slot. Then condition-arg permutations are alpha-equivalent.
count_full_local_condition(Slot,Mode,Offset,Arity):-
    selected(body,Slot,Mode),
    count_aggregate_mode(Mode),
    aggregate_mode(Mode,Arity,1),
    aggregate_condition_atom(Mode,0,_,Offset,Arity),
    not count_condition_arg_not_tuple_var(Slot,Mode,Offset,Arity),
    not count_tuple_var_used_outside(Slot).

count_condition_arg_not_tuple_var(Slot,Mode,Offset,Arity):-
    selected(body,Slot,Mode),
    aggregate_condition_atom(Mode,0,_,Offset,Arity),
    LocalArg = 0..Arity-1,
    Arg = Arity + Offset + LocalArg,
    var_at(body,Slot,Arg,Var),
    not aggregate_tuple_var(Slot,Var).

count_tuple_var_used_outside(Slot):-
    aggregate_tuple_var(Slot,Var),
    var_used_outside_body_slot(Slot,Var).

full_local_sum_condition(Slot,Mode,Offset,Arity,Weight):-
    selected(body,Slot,Mode),
    sum_aggregate_mode(Mode),
    aggregate_mode(Mode,Arity,1),
    aggregate_condition_atom(Mode,0,_,Offset,Arity),
    var_at(body,Slot,0,Weight),
    not sum_condition_arg_not_tuple_var(Slot,Mode,Offset,Arity),
    not count_tuple_var_used_outside(Slot).

sum_condition_arg_not_tuple_var(Slot,Mode,Offset,Arity):-
    selected(body,Slot,Mode),
    aggregate_condition_atom(Mode,0,_,Offset,Arity),
    LocalArg = 0..Arity-1,
    Arg = Arity + Offset + LocalArg,
    var_at(body,Slot,Arg,Var),
    not aggregate_tuple_var(Slot,Var).

aggregate_key_input_missing(Slot,Pred,Key):-
    key_arg(Key,Input),
    aggregate_condition_arg(Slot,Pred,Input,InputVar),
    not aggregate_tuple_var(Slot,InputVar).

% Constraint: for full-local #count aggregates, condition argument order is
% canonical. Reversed forms count the same assignments and are redundant.
:- count_full_local_condition(Slot,Mode,Offset,Arity),
    LocalArg0 = 0..Arity-1,
    LocalArg1 = 0..Arity-1,
    LocalArg0 < LocalArg1,
    Arg0 = Arity + Offset + LocalArg0,
    Arg1 = Arity + Offset + LocalArg1,
    var_at(body,Slot,Arg0,Left),
    var_at(body,Slot,Arg1,Right),
    Left > Right.

% Constraint: for full-local #sum aggregates, non-weight condition arguments
% are canonical. The first tuple var is the weight; only the duplicate-key vars
% are permuted, preserving the aggregate value.
:- full_local_sum_condition(Slot,Mode,Offset,Arity,Weight),
    LocalArg0 = 0..Arity-1,
    LocalArg1 = 0..Arity-1,
    LocalArg0 < LocalArg1,
    Arg0 = Arity + Offset + LocalArg0,
    Arg1 = Arity + Offset + LocalArg1,
    var_at(body,Slot,Arg0,Left),
    var_at(body,Slot,Arg1,Right),
    Left != Weight,
    Right != Weight,
    Left > Right.

% Constraint: in unbalanced aggregates, a non-weight tuple discriminator that
% is determined by condition predicate key args is redundant. The shorter
% aggregate mode represents the same count/sum elements.
:- selected(body,Slot,Mode),
    aggregate_has_shorter_mode(Mode),
    aggregate_mode(Mode,TupleArity,_),
    TupleArg = 1..TupleArity-1,
    var_at(body,Slot,TupleArg,OutputVar),
    aggregate_condition_arg(Slot,Pred,Output,OutputVar),
    key_pred(Pred,Key),
    not key_arg(Key,Output),
    not aggregate_key_input_missing(Slot,Pred,Key).

% Constraint: condition variables inside one aggregate must not repeat.
% A0/A1 range over flattened condition arguments only: TupleArity..Arity-2.
% Reusing Var inside the aggregate condition is rejected as redundant here; if
% equality is intended it should be represented by external literals/properties.
:- selected(body,Slot,Mode),
    aggregate_mode(Mode,TupleArity,_),
    mode(body,Mode,_,Arity,_),
    A0 = TupleArity..Arity-2,
    A1 = TupleArity..Arity-2,
    A0 < A1,
    var_at(body,Slot,A0,Var),
    var_at(body,Slot,A1,Var).
