% Closed-world symmetric predicate property.
%
% Python emits symmetric_pred(Pred) when binary predicate Pred is symmetric:
% Pred(X,Y) and Pred(Y,X) have same truth value. This file keeps only one
% variable orientation for selected literals and aggregate condition atoms.
%
% Shared atom shapes used here:
% - symmetric_pred(Pred): property fact for binary predicate id Pred.
% - normal_literal(Section,Slot,Mode,Pred,2): selected binary normal literal.
% - aggregate_condition_atom(Mode,AtomIndex,Pred,Offset,2): binary condition atom
%   inside aggregate mode.
% - var_at(...,0,Left) and var_at(...,1,Right): binary argument variables.
% - aggregate_condition_arg(Slot,Pred,LocalArg,Var): aggregate condition arg.

% Python fact contract:
% - symmetric_pred(Pred): emitted by Python when binary predicate id Pred is
%   symmetric in closed-world evidence.
% - aggregate_condition_atom(Mode,AtomIndex,Pred,Offset,Arity): emitted by
%   Python for aggregate condition atoms so symmetric pruning also applies
%   inside aggregate conditions.
% Python fact detail: symmetric_pred(Pred) marks binary predicate id Pred as symmetric.
#defined symmetric_pred/1.
% Python fact detail: aggregate_condition_atom(Mode,AtomIndex,Pred,Offset,Arity) describes one aggregate condition atom; Offset is flattened arg offset.
#defined aggregate_condition_atom/5.

% Constraint: normal symmetric literals use nondecreasing variable order.
% Section/Slot/Mode identify selected binary normal literal. Left is argument 0,
% Right is argument 1. Left > Right would encode same literal as reversed order.
:- selected(Section,Slot,Mode),
    normal_literal(Section,Slot,Mode,Pred,2),
    symmetric_pred(Pred),
    var_at(Section,Slot,0,Left),
    var_at(Section,Slot,1,Right),
    Left > Right.

% Constraint: aggregate condition symmetric atoms use nondecreasing order.
% Slot is aggregate body slot. Pred is binary symmetric condition predicate.
% Left/Right are local condition arguments 0 and 1. Descending variable order is
% redundant because Pred is symmetric.
:- selected(body,Slot,Mode),
    aggregate_condition_atom(Mode,_,Pred,Offset,2),
    symmetric_pred(Pred),
    aggregate_condition_arg(Slot,Pred,0,Left),
    aggregate_condition_arg(Slot,Pred,1,Right),
    Left > Right.
