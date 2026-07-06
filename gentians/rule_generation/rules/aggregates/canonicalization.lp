% Aggregate canonicalization.
%
% This file removes aggregate encodings that are invalid or redundant:
% duplicated tuple variables, descending count tuple variables, and duplicated
% condition variables inside one aggregate condition.
%
% Shared atom shapes used here:
% - aggregate_mode(Mode,TupleArity,AtomCount): Python fact for aggregate modes.
% - count_aggregate_mode(Mode): Python fact for count aggregates.
% - canonical_prune: Python fact enabling optional canonical pruning.
% - selected(body,Slot,Mode): selected body aggregate.
% - mode(body,Mode,Pred,Arity,Recall): flattened arity for aggregate Mode.
% - var_at(body,Slot,Arg,Var): variable assignment.

% Python fact contract:
% - aggregate_mode(Mode,TupleArity,AtomCount): emitted by Python for aggregate
%   modes. TupleArity splits tuple args from condition args.
% - count_aggregate_mode(Mode): emitted by Python when Mode renders as #count.
% - canonical_prune: emitted by Python when optional canonical pruning is on.
% Python fact detail: aggregate_mode(Mode,TupleArity,AtomCount) marks aggregate modes; TupleArity is grouped tuple length, AtomCount is condition atom count.
#defined aggregate_mode/3.
% Python fact detail: count_aggregate_mode(Mode) marks aggregate modes rendered as #count.
#defined count_aggregate_mode/1.
% Python fact detail: canonical_prune is emitted when optional canonical duplicate pruning is enabled.
#defined canonical_prune/0.

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
% so descending variable ids are rejected when canonical_prune is enabled.
:- canonical_prune,
    selected(body,Slot,Mode),
    count_aggregate_mode(Mode),
    aggregate_mode(Mode,TupleArity,_),
    A0 = 0..TupleArity-1,
    A1 = 0..TupleArity-1,
    A0 < A1,
    var_at(body,Slot,A0,Left),
    var_at(body,Slot,A1,Right),
    Left > Right.

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
