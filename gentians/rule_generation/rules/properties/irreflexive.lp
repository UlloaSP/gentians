% Closed-world irreflexive predicate property.
%
% This file owns only irreflexive pruning: reject positive self-pairs
% Pred(Var,Var). Stronger properties such as asymmetric, acyclic, and
% strict_order derive irreflexive_pred(Pred) in their own files.
%
% Shared atom shapes used here:
% - irreflexive_pred(Pred): property atom for binary predicate id Pred.
% - positive_body_literal(Slot,Mode,Pred,2): selected positive binary body atom.
% - var_at(body,Slot,Arg,Var): binary argument assignment.

% Constraint: reject self-pair for irreflexive predicates.
% Slot is positive binary literal Pred(Var,Var). Such self-loops contradict
% any property source that derived irreflexive_pred(Pred).
:- positive_body_literal(Slot,_,Pred,2),
    irreflexive_pred(Pred),
    var_at(body,Slot,0,Var),
    var_at(body,Slot,1,Var).
