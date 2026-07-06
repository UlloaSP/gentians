% Closed-world antisymmetric-like predicate property.
%
% Python emits antisymmetric_pred/1, strict_order_pred/1, total_order_pred/1,
% and acyclic_pred/1 from closed-world evidence. All of these reject two
% positive body literals Pred(X,Y) and Pred(Y,X) for X != Y.
%
% Shared atom shapes used here:
% - antisymmetric_pred(Pred): explicit antisymmetric predicate id.
% - strict_order_pred(Pred): strict order predicate id; strict orders are
%   antisymmetric-like.
% - total_order_pred(Pred): total order predicate id; total orders are
%   antisymmetric-like for distinct variables.
% - acyclic_pred(Pred): acyclic binary predicate id; reversed two-edge cycles
%   are impossible.
% - antisymmetric_like_pred(Pred): local union alias.
% - positive_body_literal(Slot,Mode,Pred,2): selected positive binary body atom.
% - var_at(body,Slot,Arg,Var): Arg 0 is left variable; Arg 1 is right variable.

% Python fact contract:
% - antisymmetric_pred(Pred): emitted by Python when binary predicate id Pred is
%   antisymmetric in observed facts.
% - strict_order_pred(Pred): emitted by Python when Pred behaves as strict order.
% - total_order_pred(Pred): emitted by Python when Pred behaves as total order.
% - acyclic_pred(Pred): emitted by Python when Pred is acyclic; used here
%   because reversed positive pairs create a cycle.
% Python fact detail: antisymmetric_pred(Pred) marks binary predicate id Pred as antisymmetric.
#defined antisymmetric_pred/1.
% Python fact detail: strict_order_pred(Pred) marks binary predicate id Pred as strict order.
#defined strict_order_pred/1.
% Python fact detail: total_order_pred(Pred) marks binary predicate id Pred as total order.
#defined total_order_pred/1.
% Python fact detail: acyclic_pred(Pred) marks binary predicate id Pred as acyclic in closed-world evidence.
#defined acyclic_pred/1.

% Rule: explicit antisymmetric predicates are antisymmetric-like.
% Pred is predicate id.
antisymmetric_like_pred(Pred):- antisymmetric_pred(Pred).

% Rule: strict order predicates are antisymmetric-like.
% Pred is predicate id.
antisymmetric_like_pred(Pred):- strict_order_pred(Pred).

% Rule: total order predicates are antisymmetric-like.
% Pred is predicate id.
antisymmetric_like_pred(Pred):- total_order_pred(Pred).

% Rule: acyclic predicates are antisymmetric-like for two-edge cycles.
% Pred is predicate id.
antisymmetric_like_pred(Pred):- acyclic_pred(Pred).

% Constraint: reject positive reversed pair for antisymmetric-like predicates.
% Slot0 and Slot1 are ordered positive binary body literals over same Pred.
% Slot0 is Pred(Left,Right), Slot1 is Pred(Right,Left). Left != Right excludes
% self-pairs, which are handled by irreflexive/reflexive/total-order modules.
:- positive_body_literal(Slot0,_,Pred,2),
    positive_body_literal(Slot1,_,Pred,2),
    Slot0 < Slot1,
    antisymmetric_like_pred(Pred),
    var_at(body,Slot0,0,Left),
    var_at(body,Slot0,1,Right),
    Left != Right,
    var_at(body,Slot1,0,Right),
    var_at(body,Slot1,1,Left).
