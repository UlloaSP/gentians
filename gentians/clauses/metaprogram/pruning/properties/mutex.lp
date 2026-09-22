% Mutex predicates cannot both hold on the same terms. A positive member also
% makes negation of its partner redundant. Strong complements p/n and -p/n use
% this same rule; two default-negated members remain available.

#defined strong_complement_pred/2.
#defined mutex_pred/2.

mutex_pred(Pred0, Pred1) :- strong_complement_pred(Pred0, Pred1).

mutex_pair(Pred0, Pred1) :- mutex_pred(Pred0, Pred1).

mutex_pair(Pred1, Pred0) :- mutex_pred(Pred0, Pred1).

:- positive_body_literal(Slot0, _, Pred0, Arity),
    positive_body_literal(Slot1, _, Pred1, Arity),
    Slot0 < Slot1,
    mutex_pair(Pred0, Pred1),
    same_term_bindings(body, Slot0, body, Slot1).

:- positive_body_literal(Slot0, _, Pred0, Arity),
    negative_body_literal(Slot1, _, Pred1, Arity),
    Slot0 != Slot1,
    mutex_pair(Pred0, Pred1),
    same_term_bindings(body, Slot0, body, Slot1).
