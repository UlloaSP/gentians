% Closed-world antisymmetric predicate property.
%
% This file owns only antisymmetric pruning: reject two positive body literals
% Pred(X, Y) and Pred(Y, X) for distinct variable ids. Antisymmetry forces equal
% values; this is variable-identification pruning, not proof of unequal values.
% Stronger properties such as asymmetric,
% acyclic, strict_order, and total_order derive antisymmetric_pred(Pred) in
% their own files.


% CONSTRAINT. An antisymmetric predicate may not be written in both directions
% over two different variable ids. The pair is satisfiable only when both
% values are equal, which the enumerator expresses by writing one id.
%   Slot0 < Slot1  body slots of the two positive atoms.
%   Pred           the antisymmetric binary predicate.
%   Left, Right    two different variable ids: Pred(Left,Right) at Slot0 and
%                  Pred(Right,Left) at Slot1.
% With le/2 antisymmetric:
%   pruned: h(V0) :- le(V0,V1), le(V1,V0).
%   kept:   h(V0) :- le(V0,V0).               the same meaning with one id
%   kept:   h(V0) :- le(V0,V1), le(V1,V2).
:- positive_body_literal(Slot0, _, Pred, 2),
    positive_body_literal(Slot1, _, Pred, 2),
    Slot0 < Slot1,
    antisymmetric_pred(Pred),
    var_at(body, Slot0, 0, Left),
    var_at(body, Slot0, 1, Right),
    Left != Right,
    var_at(body, Slot1, 0, Right),
    var_at(body, Slot1, 1, Left).
