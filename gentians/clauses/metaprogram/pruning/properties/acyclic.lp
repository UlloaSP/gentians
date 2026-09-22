% Acyclic relations exclude self-pairs, reversed pairs and positive triangles.
% The first two checks are delegated to irreflexive/antisymmetric properties.
% A negated back-edge over a positive two-step path is redundant.

#defined acyclic_pred/1.

irreflexive_pred(Pred) :- acyclic_pred(Pred).

antisymmetric_pred(Pred) :- acyclic_pred(Pred).

:- positive_body_literal(Slot0, _, Pred, 2),
    positive_body_literal(Slot1, _, Pred, 2),
    positive_body_literal(Slot2, _, Pred, 2),
    Slot0 < Slot1,
    Slot1 < Slot2,
    acyclic_pred(Pred),
    var_at(body, Slot0, 0, X),
    var_at(body, Slot0, 1, Y),
    var_at(body, Slot1, 0, Y),
    var_at(body, Slot1, 1, Z),
    var_at(body, Slot2, 0, Z),
    var_at(body, Slot2, 1, X).

:- positive_body_literal(Slot0, _, Pred, 2),
    positive_body_literal(Slot1, _, Pred, 2),
    negative_body_literal(Slot2, _, Pred, 2),
    acyclic_pred(Pred),
    var_at(body, Slot0, 0, X),
    var_at(body, Slot0, 1, Y),
    var_at(body, Slot1, 0, Y),
    var_at(body, Slot1, 1, Z),
    var_at(body, Slot2, 0, Z),
    var_at(body, Slot2, 1, X).
