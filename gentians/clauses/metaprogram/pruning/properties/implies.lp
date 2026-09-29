% Closed-world implication property.
%
% Python emits implies_pred(Pred0, Pred1) when Pred0(X...) implies Pred1(X...)
% for same-arity predicates. Other property files may derive implies_pred/2
% when they imply it. Target may be a learned predicate whose background lower
% bound already contains Source: learned clauses only add to it. This file prunes
% body literals made redundant or impossible by a positive body literal, and a
% plain head that the body already guarantees. A choice or aggregate head is not
% redundant that way: 0{q(X);s(X)}1 :- p(X) still forbids s(X) when p implies q.


:- positive_body_literal(Slot0, _, Pred0, Arity),
    positive_body_literal(Slot1, _, Pred1, Arity),
    Slot0 != Slot1,
    implies_pred(Pred0, Pred1),
    same_term_bindings(body, Slot0, body, Slot1).

:- positive_body_literal(Slot0, _, Pred0, Arity),
    head_literal(Slot1, Mode, Pred1, Arity),
    plain_disjunctive_head_mode(Mode),
    implies_pred(Pred0, Pred1),
    same_term_bindings(body, Slot0, head, Slot1).

:- positive_body_literal(Slot0, _, Pred0, Arity),
    negative_body_literal(Slot1, _, Pred1, Arity),
    Slot0 != Slot1,
    implies_pred(Pred0, Pred1),
    same_term_bindings(body, Slot0, body, Slot1).
