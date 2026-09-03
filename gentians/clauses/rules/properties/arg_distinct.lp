% Closed-world argument distinctness property.
%
% Python emits arg_distinct_pred(Pred,Arg0,Arg1) when every true tuple of
% predicate Pred has different values at positions Arg0 and Arg1. Other
% property files may derive arg_distinct_pred/3 when they imply it; for example
% irreflexive.lp derives arg_distinct_pred(Pred,0,1) for binary predicates.
% This file rejects generated literals that assign the same variable to those
% positions.
%
% Shared atom shapes used here:
% - arg_distinct_pred(Pred,Arg0,Arg1): property fact or derived atom. Pred is
%   predicate id; Arg0 and Arg1 are zero-based positions that must differ.
% - normal_literal/5, aggregate_condition_atom/5, aggregate_condition_arg/4,
%   and var_at/4 have same meaning as in arg_equal.lp.

% Python fact contract:
% - arg_distinct_pred(Pred,Arg0,Arg1): emitted by Python when predicate id Pred
%   always has different values at zero-based argument positions Arg0 and Arg1.
%   Other ASP property files may also derive arg_distinct_pred/3 from stronger
%   properties.
% - aggregate_condition_atom(Mode,AtomIndex,Pred,Offset,Arity): emitted by
%   Python for aggregate condition atoms so the same property can prune inside
%   aggregates.
% Python fact detail: arg_distinct_pred(Pred,Arg0,Arg1) means arguments Arg0 and Arg1 of Pred must be different.
#defined arg_distinct_pred/3.
% Python fact detail: aggregate_condition_atom(Mode,AtomIndex,Pred,Offset,Arity) describes one aggregate condition atom; Offset is flattened arg offset.
#defined aggregate_condition_atom/5.

% Rule: positive binary self-pair already handled by irreflexive.lp.
% Slot/Mode/Pred identify a positive body literal Pred(Var,Var). If
% irreflexive_pred(Pred) holds, irreflexive.lp owns this body-pruning case.
arg_distinct_self_pair_owned_by_irreflexive(Slot,Mode,Pred):-
    positive_body_literal(Slot,Mode,Pred,2),
    irreflexive_pred(Pred).

% Constraint: normal literal must not reuse one variable in distinct positions.
% Section/Slot/Mode identify selected normal literal. Pred owns distinctness
% property. Arg0 and Arg1 are positions. Var is same generated variable at both
% positions, contradicting arg_distinct_pred. Only positive binary body
% self-pairs already owned by irreflexive.lp are skipped.
:- selected(Section,Slot,Mode),
    normal_literal(Section,Slot,Mode,Pred,_),
    arg_distinct_pred(Pred,Arg0,Arg1),
    var_at(Section,Slot,Arg0,Var),
    var_at(Section,Slot,Arg1,Var),
    not arg_distinct_self_pair_owned_by_irreflexive(Slot,Mode,Pred).

% Constraint: aggregate condition atom must not reuse one variable in distinct
% local positions. LocalArg0 and LocalArg1 refer to the condition atom's own
% argument indexes. Var at both positions violates arg_distinct_pred.
:- selected(body,Slot,Mode),
    aggregate_condition_atom(Mode,_,Pred,Offset,_),
    arg_distinct_pred(Pred,LocalArg0,LocalArg1),
    aggregate_condition_arg(Slot,Pred,LocalArg0,Var),
    aggregate_condition_arg(Slot,Pred,LocalArg1,Var).
