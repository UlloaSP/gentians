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

% CONSTRAINT. A positive atom and the positive atom of its inverse over the
% swapped variables say the same thing; the second is redundant.
%   Slot0 < Slot1  body slots of the two positive binary atoms.
%   Pred0, Pred1   an inverse pair.
%   pruned: h(V0) :- parent(V0,V1), child(V1,V0).
%   kept:   h(V0) :- parent(V0,V1).                  the same meaning
%   kept:   h(V0) :- parent(V0,V1), child(V0,V1).    not swapped
:- positive_body_literal(Slot0, _, Pred0, 2),
    positive_body_literal(Slot1, _, Pred1, 2),
    Slot0 < Slot1,
    inverse_pair(Pred0, Pred1),
    reversed_binary_vars(body, Slot0, body, Slot1).

% CONSTRAINT. A positive atom together with the negation of its inverse over
% the swapped variables makes the body unsatisfiable.
%   Slot0  body slot of the positive atom, of Pred0.
%   Slot1  body slot of the negated atom, of Pred1.
%   pruned: h(V0) :- parent(V0,V1), not child(V1,V0).
%   kept:   h(V0) :- parent(V0,V1), not child(V0,V1).
:- positive_body_literal(Slot0, _, Pred0, 2),
    negative_body_literal(Slot1, _, Pred1, 2),
    inverse_pair(Pred0, Pred1),
    reversed_binary_vars(body, Slot0, body, Slot1).
