% Closed-world argument distinctness property.
%
% Python emits arg_distinct_pred(Pred,Arg0,Arg1) when every true tuple of
% predicate Pred has different values at positions Arg0 and Arg1. This file
% rejects generated literals that assign the same variable to those positions.
%
% Shared atom shapes used here:
% - arg_distinct_pred(Pred,Arg0,Arg1): property fact. Pred is predicate id; Arg0
%   and Arg1 are zero-based positions that must differ.
% - normal_literal/5, aggregate_condition_atom/5, aggregate_condition_arg/4,
%   and var_at/4 have same meaning as in arg_equal.lp.

#defined arg_distinct_pred/3.
#defined aggregate_condition_atom/5.

% Constraint: normal literal must not reuse one variable in distinct positions.
% Section/Slot/Mode identify selected normal literal. Pred owns distinctness
% property. Arg0 and Arg1 are positions. Var is same generated variable at both
% positions, contradicting arg_distinct_pred.
:- selected(Section,Slot,Mode),
    normal_literal(Section,Slot,Mode,Pred,_),
    arg_distinct_pred(Pred,Arg0,Arg1),
    var_at(Section,Slot,Arg0,Var),
    var_at(Section,Slot,Arg1,Var).

% Constraint: aggregate condition atom must not reuse one variable in distinct
% local positions. LocalArg0 and LocalArg1 refer to the condition atom's own
% argument indexes. Var at both positions violates arg_distinct_pred.
:- selected(body,Slot,Mode),
    aggregate_condition_atom(Mode,_,Pred,Offset,_),
    arg_distinct_pred(Pred,LocalArg0,LocalArg1),
    aggregate_condition_arg(Slot,Pred,LocalArg0,Var),
    aggregate_condition_arg(Slot,Pred,LocalArg1,Var).
