% Closed-world total order predicate property.
%
% Python emits total_order_pred(Pred) when binary predicate Pred behaves like a
% total order over its observed domain. A total order is reflexive,
% antisymmetric, and transitive; this file exports those base-property atoms and
% keeps only the totality-specific pruning.

#defined total_order_pred/1.

reflexive_pred(Pred) :- total_order_pred(Pred).

antisymmetric_pred(Pred) :- total_order_pred(Pred).

transitive_pred(Pred) :- total_order_pred(Pred).

:- negative_body_literal(Slot0, _, Pred, 2),
    negative_body_literal(Slot1, _, Pred, 2),
    Slot0 < Slot1,
    total_order_pred(Pred),
    var_at(body, Slot0, 0, Left),
    var_at(body, Slot0, 1, Right),
    Left != Right,
    var_at(body, Slot1, 0, Right),
    var_at(body, Slot1, 1, Left).
