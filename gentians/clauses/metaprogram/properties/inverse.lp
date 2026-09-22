% Closed-world inverse predicate property.
%
% Python emits inverse_pred(Pred0,Pred1) when two binary predicates are inverses:
% Pred0(X,Y) has same truth value as Pred1(Y,X). This file removes redundant
% positive inverse pairs and contradictory positive/negative inverse pairs.

#defined inverse_pred/2.

inverse_pair(Pred0,Pred1):- inverse_pred(Pred0,Pred1).

inverse_pair(Pred1,Pred0):- inverse_pred(Pred0,Pred1).

:- positive_body_literal(Slot0,_,Pred0,2),
    positive_body_literal(Slot1,_,Pred1,2),
    Slot0 < Slot1,
    inverse_pair(Pred0,Pred1),
    reversed_binary_vars(body,Slot0,body,Slot1).

:- positive_body_literal(Slot0,_,Pred0,2),
    negative_body_literal(Slot1,_,Pred1,2),
    inverse_pair(Pred0,Pred1),
    reversed_binary_vars(body,Slot0,body,Slot1).
