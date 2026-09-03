% Closed-world antisymmetric predicate property.
%
% This file owns only antisymmetric pruning: reject two positive body literals
% Pred(X,Y) and Pred(Y,X) for X != Y. Stronger properties such as asymmetric,
% acyclic, strict_order, and total_order derive antisymmetric_pred(Pred) in
% their own files.
%
% Shared atom shapes used here:
% - antisymmetric_pred(Pred): property atom for binary predicate id Pred.
% - positive_body_literal(Slot,Mode,Pred,2): selected positive binary body atom.
% - var_at(body,Slot,Arg,Var): Arg 0 is left variable; Arg 1 is right variable.

% Python fact contract:
% - antisymmetric_pred(Pred): emitted by Python when binary predicate id Pred is
%   directly antisymmetric in observed facts. Other ASP property files may also
%   derive antisymmetric_pred(Pred) when their stronger property implies it.
% Python fact detail: antisymmetric_pred(Pred) marks binary predicate id Pred as antisymmetric.
#defined antisymmetric_pred/1.

% Constraint: reject positive reversed pair for antisymmetric predicates.
% Slot0 and Slot1 are ordered positive binary body literals over same Pred.
% Slot0 is Pred(Left,Right), Slot1 is Pred(Right,Left). Left != Right excludes
% self-pairs, which are handled by irreflexive/reflexive/total-order modules.
:- positive_body_literal(Slot0,_,Pred,2),
    positive_body_literal(Slot1,_,Pred,2),
    Slot0 < Slot1,
    antisymmetric_pred(Pred),
    var_at(body,Slot0,0,Left),
    var_at(body,Slot0,1,Right),
    Left != Right,
    var_at(body,Slot1,0,Right),
    var_at(body,Slot1,1,Left).
