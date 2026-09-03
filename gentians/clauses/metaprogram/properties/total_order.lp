% Closed-world total order predicate property.
%
% Python emits total_order_pred(Pred) when binary predicate Pred behaves like a
% total order over its observed domain. A total order is reflexive,
% antisymmetric, and transitive; this file exports those base-property atoms and
% keeps only the totality-specific pruning.
%
% Shared atom shapes used here:
% - total_order_pred(Pred): property fact for binary predicate id.
% - reflexive_pred(Pred): derived property atom consumed by reflexive.lp.
% - antisymmetric_pred(Pred): derived property atom consumed by antisymmetric.lp.
% - transitive_pred(Pred): derived property atom consumed by transitive.lp.
% - negative_body_literal(Slot,Mode,Pred,2): selected negated binary body atom.
% - var_at(body,Slot,Arg,Var): binary argument variables.

% Python fact contract:
% - total_order_pred(Pred): emitted by Python when binary predicate id Pred
%   behaves as total order over observed typed domain.
% Python fact detail: total_order_pred(Pred) marks binary predicate id Pred as total order.
#defined total_order_pred/1.

% Rule: total orders are reflexive.
% Pred is the predicate id. reflexive.lp owns positive/negative self-pair
% pruning for reflexive predicates.
reflexive_pred(Pred):- total_order_pred(Pred).

% Rule: total orders are antisymmetric.
% Pred is the predicate id. antisymmetric.lp owns reversed-pair pruning.
antisymmetric_pred(Pred):- total_order_pred(Pred).

% Rule: total orders are transitive.
% Pred is the predicate id. transitive.lp owns transitive closure pruning.
transitive_pred(Pred):- total_order_pred(Pred).

% Constraint: reject negating both directions of a total order.
% Slot0 is not Pred(Left,Right); Slot1 is not Pred(Right,Left). Left != Right
% means distinct variables. In a total order at least one direction must hold.
:- negative_body_literal(Slot0,_,Pred,2),
    negative_body_literal(Slot1,_,Pred,2),
    Slot0 < Slot1,
    total_order_pred(Pred),
    var_at(body,Slot0,0,Left),
    var_at(body,Slot0,1,Right),
    Left != Right,
    var_at(body,Slot1,0,Right),
    var_at(body,Slot1,1,Left).
