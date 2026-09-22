% Closed-world antisymmetric predicate property.
%
% This file owns only antisymmetric pruning: reject two positive body literals
% Pred(X, Y) and Pred(Y, X) for distinct variable ids. Antisymmetry forces equal
% values; this is variable-identification pruning, not proof of unequal values.
% Stronger properties such as asymmetric,
% acyclic, strict_order, and total_order derive antisymmetric_pred(Pred) in
% their own files.


:- positive_body_literal(Slot0, _, Pred, 2),
    positive_body_literal(Slot1, _, Pred, 2),
    Slot0 < Slot1,
    antisymmetric_pred(Pred),
    var_at(body, Slot0, 0, Left),
    var_at(body, Slot0, 1, Right),
    Left != Right,
    var_at(body, Slot1, 0, Right),
    var_at(body, Slot1, 1, Left).
