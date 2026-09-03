% Closed-world irreflexive predicate property.
%
% This file owns irreflexive knowledge: reject positive self-pairs Pred(Var,Var)
% and export the equivalent argument-distinct property for binary predicates.
% Stronger properties such as asymmetric, acyclic, and strict_order derive
% irreflexive_pred(Pred) in their own files.
%
% Shared atom shapes used here:
% - irreflexive_pred(Pred): property atom for binary predicate id Pred.
% - arg_distinct_pred(Pred,0,1): derived property consumed by arg_distinct.lp.
% - positive_body_literal(Slot,Mode,Pred,2): selected positive binary body atom.
% - var_at(body,Slot,Arg,Var): binary argument assignment.

% Rule: irreflexive binary predicates have distinct arguments in true tuples.
% Pred is a binary predicate id. If Pred(X,X) is impossible, any true Pred tuple
% must have argument 0 different from argument 1. arg_distinct.lp owns the
% non-body-positive contexts such as heads, negated literals, and aggregates.
arg_distinct_pred(Pred,0,1):- irreflexive_pred(Pred).

% Constraint: reject self-pair for irreflexive predicates.
% Slot is positive binary literal Pred(Var,Var). Such self-loops contradict
% any property source that derived irreflexive_pred(Pred).
:- positive_body_literal(Slot,_,Pred,2),
    irreflexive_pred(Pred),
    var_at(body,Slot,0,Var),
    var_at(body,Slot,1,Var).
