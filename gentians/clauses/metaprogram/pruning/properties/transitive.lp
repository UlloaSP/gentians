% Closed-world transitive predicate property.
%
% This file owns transitive pruning: reject explicit transitive-closure
% redundancies and negative literals contradicting such closure. Stronger
% properties such as strict_order and total_order derive transitive_pred(Pred)
% in their own files.


:- positive_body_literal(Slot0, _, Pred, 2),
    positive_body_literal(Slot1, _, Pred, 2),
    positive_body_literal(Slot2, _, Pred, 2),
    Slot0 < Slot1,
    Slot1 < Slot2,
    transitive_pred(Pred),
    var_at(body, Slot0, 0, X),
    var_at(body, Slot0, 1, Y),
    var_at(body, Slot1, 0, Y),
    var_at(body, Slot1, 1, Z),
    var_at(body, Slot2, 0, X),
    var_at(body, Slot2, 1, Z).

:- positive_body_literal(Slot0, _, Pred, 2),
    positive_body_literal(Slot1, _, Pred, 2),
    negative_body_literal(Slot2, _, Pred, 2),
    transitive_pred(Pred),
    var_at(body, Slot0, 0, X),
    var_at(body, Slot0, 1, Y),
    var_at(body, Slot1, 0, Y),
    var_at(body, Slot1, 1, Z),
    var_at(body, Slot2, 0, X),
    var_at(body, Slot2, 1, Z).
