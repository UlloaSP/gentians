% Closed-world inverse predicate property.
%
% Python emits inverse_pred(Pred0, Pred1) when two binary predicates are inverses:
% Pred0(X, Y) has same truth value as Pred1(Y, X). This file removes redundant
% positive inverse pairs and contradictory positive/negative inverse pairs.
%
% The examples assume inverse_pred(parent,child).


% DEFINITION, local helper. inverse_pair(Pred0, Pred1): the two predicates are
% inverses, available in both orders.
%   Pred0, Pred1  signed predicate ids of an inverse pair.
% Python emits each pair once; the constraints below must match whichever
% predicate they meet first. Used only by those constraints.
% Case 1: the emitted order.
inverse_pair(Pred0, Pred1) :- inverse_pred(Pred0, Pred1).

% DEFINITION, local helper. Same predicate. Case 2: the reversed order.
inverse_pair(Pred1, Pred0) :- inverse_pred(Pred0, Pred1).

% DEFINITION, local helper. inverse_swapped(Slot0, Slot1): two body atoms of
% an inverse pair hold the same two variables, swapped.
%   Slot0  body slot of a plain atom Pred0(Left, Right), of either polarity.
%   Slot1  a different body slot, of a plain atom Pred1(Right, Left) whose
%          predicate is the inverse of Pred0.
% Example: parent(V0,V1) and child(V1,V0). It is derived only for inverse
% pairs, so tasks without them ground nothing. Used only by the two
% constraints below.
inverse_swapped(Slot0, Slot1) :-
    normal_literal(body, Slot0, _, Pred0, 2),
    normal_literal(body, Slot1, _, Pred1, 2),
    inverse_pair(Pred0, Pred1),
    Slot0 != Slot1,
    var_at(body, Slot0, 0, Left),
    var_at(body, Slot0, 1, Right),
    var_at(body, Slot1, 0, Right),
    var_at(body, Slot1, 1, Left).

% DEFINITION, local helper. inverse_duplicate(Slot0, Slot1): two positive
% body atoms of an inverse pair say the same thing.
%   Slot0 < Slot1  body slots of the two positive binary atoms, over swapped
%                  variables.
% Used only by the two constraints below, which differ in which of the two
% atoms the shorter clause would lose.
inverse_duplicate(Slot0, Slot1) :-
    positive_body_literal(Slot0, _, _, 2),
    positive_body_literal(Slot1, _, _, 2),
    Slot0 < Slot1,
    inverse_swapped(Slot0, Slot1).

% CONSTRAINT. A positive atom and the positive atom of its inverse over the
% swapped variables say the same thing; one of them is redundant. Here the
% later atom is the one that directed flow does not need.
%   Slot0, Slot1  the duplicated pair.
%   pruned: h(V0) :- parent(V0,V1), child(V1,V0).
%   kept:   h(V0) :- parent(V0,V1).                  the same meaning
%   kept:   h(V0) :- parent(V0,V1), child(V0,V1).    not swapped
:- inverse_duplicate(Slot0, Slot1), not flow_needed(Slot1).

% CONSTRAINT. The same pair when the earlier atom is the one that directed
% flow does not need. The clause stays only if both atoms are needed.
%   Slot0, Slot1  the duplicated pair.
:- inverse_duplicate(Slot0, Slot1), not flow_needed(Slot0).

% CONSTRAINT. A positive atom together with the negation of its inverse over
% the swapped variables makes the body unsatisfiable.
%   Slot0  body slot of the positive atom, of Pred0.
%   Slot1  body slot of the negated atom, of Pred1.
%   pruned: h(V0) :- parent(V0,V1), not child(V1,V0).
%   kept:   h(V0) :- parent(V0,V1), not child(V0,V1).
:- positive_body_literal(Slot0, _, Pred0, 2),
    negative_body_literal(Slot1, _, Pred1, 2),
    inverse_swapped(Slot0, Slot1).
