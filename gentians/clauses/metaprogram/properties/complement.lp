% Closed-world complement predicate property.
%
% Python emits complement_pred(Pred0,Pred1) when same-arity predicates are
% logical complements. Complements are also mutex, so this file exports
% mutex_pred/2 and keeps the complement-specific double-negative constraint.

#defined complement_pred/2.

complement_pair(Pred0,Pred1):- complement_pred(Pred0,Pred1).

complement_pair(Pred1,Pred0):- complement_pred(Pred0,Pred1).

mutex_pred(Pred0,Pred1):- complement_pred(Pred0,Pred1).

:- negative_body_literal(Slot0,_,Pred0,Arity),
    negative_body_literal(Slot1,_,Pred1,Arity),
    Slot0 < Slot1,
    complement_pair(Pred0,Pred1),
    same_vars(body,Slot0,body,Slot1).
