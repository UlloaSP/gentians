% Closed-world equivalent predicate property.
%
% Python emits equivalent_pred(Pred0, Pred1) when two predicates with same arity
% have identical truth values for same argument tuple. Equivalence is
% implication in both directions, so this file exports implies_pred/2. It keeps
% only equivalent-specific duplicate pruning that implication cannot express:
% duplicate negated body literals. Head predicates are learned, so no property
% fact ever names them.


% DEFINITION, local helper. equivalent_pair(Pred0, Pred1): the two predicates
% are equivalent, available in both orders.
%   Pred0, Pred1  signed predicate ids of an equivalent pair.
% Python emits each pair once; the constraint below must match whichever
% predicate sits in the earlier slot. Used only by that constraint.
% Case 1: the emitted order.
equivalent_pair(Pred0, Pred1) :- equivalent_pred(Pred0, Pred1).

% DEFINITION, local helper. Same predicate. Case 2: the reversed order.
equivalent_pair(Pred1, Pred0) :- equivalent_pred(Pred0, Pred1).

% DEFINITION, reusable property bridge. implies_pred(Pred0, Pred1): every
% tuple of Pred0 is a tuple of Pred1.
%   Pred0, Pred1  signed predicate ids of an equivalent pair.
% Equivalence is implication both ways. The positive-literal checks are owned
% by pruning/properties/implies.lp.
% Case 1: left implies right.
implies_pred(Pred0, Pred1) :- equivalent_pred(Pred0, Pred1).

% DEFINITION, reusable property bridge. Same predicate. Case 2: right implies
% left.
implies_pred(Pred1, Pred0) :- equivalent_pred(Pred0, Pred1).

% CONSTRAINT. Two equivalent predicates may not both be negated on the same
% arguments: the second negation repeats the first.
%   Slot0 < Slot1  body slots of the two negated atoms, with identical
%                  arguments.
%   Pred0, Pred1   an equivalent pair.
% With equivalent_pred(adult,grown):
%   pruned: h(V0) :- d(V0), not adult(V0), not grown(V0).
%   kept:   h(V0) :- d(V0), not adult(V0).
:- negative_body_literal(Slot0, _, Pred0, Arity),
    negative_body_literal(Slot1, _, Pred1, Arity),
    Slot0 < Slot1,
    equivalent_pair(Pred0, Pred1),
    same_term_bindings(body, Slot0, body, Slot1).
