% Closed-world transitive predicate property.
%
% This file owns transitive pruning: reject explicit transitive-closure
% redundancies and negative literals contradicting such closure. Stronger
% properties such as strict_order and total_order derive transitive_pred(Pred)
% in their own files.


% CONSTRAINT. After a positive path X->Y->Z of a transitive predicate, the
% positive shortcut Pred(X,Z) is entailed and therefore redundant.
%   Slot0 < Slot1 < Slot2  body slots of Pred(X,Y), Pred(Y,Z) and the shortcut
%                          Pred(X,Z), in that slot order.
%   Pred                   a transitive binary predicate.
%   X, Y, Z                variable ids.
% The pattern requires the shortcut in the last of the three slots:
%   pruned: a body whose slots hold, in order, lt(X,Y), lt(Y,Z), lt(X,Z)
%   kept:   :- lt(V0,V1), lt(V1,V2).
% symmetry/slots.lp sorts atoms of one mode by their variable tuples, which
% places (X,Z) before (Y,Z). With the three atoms selected through a single
% mode the pattern therefore never matches, and
% ":- lt(V0,V1), lt(V0,V2), lt(V1,V2)." is kept; it can match only when the
% atoms come from different modes of Pred.
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

% CONSTRAINT. After a positive path X->Y->Z of a transitive predicate,
% negating the shortcut Pred(X,Z) makes the body unsatisfiable.
%   Slot0, Slot1  body slots of the positive atoms Pred(X,Y) and Pred(Y,Z),
%                 in any slot order.
%   Slot2         body slot of "not Pred(X,Z)".
%   X, Y, Z       variable ids.
% With lt/2 transitive:
%   pruned: :- lt(V0,V1), lt(V1,V2), not lt(V0,V2).
%   kept:   :- lt(V0,V1), lt(V1,V2), not lt(V2,V0).   not the shortcut (for a
%                                                     strict order acyclic.lp
%                                                     rejects this one)
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
