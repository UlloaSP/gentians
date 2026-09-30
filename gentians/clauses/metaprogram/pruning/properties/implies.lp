% Closed-world implication property.
%
% Python emits implies_pred(Pred0, Pred1) when Pred0(X...) implies Pred1(X...)
% for same-arity predicates. Other property files may derive implies_pred/2
% when they imply it. Target may be a learned predicate whose background lower
% bound already contains Source: learned clauses only add to it. This file prunes
% body literals made redundant or impossible by a positive body literal, and a
% plain head that the body already guarantees. A choice or aggregate head is not
% redundant that way: 0{q(X);s(X)}1 :- p(X) still forbids s(X) when p implies q.
%
% The examples assume implies_pred(parent,ancestor): every parent tuple is an
% ancestor tuple.


% CONSTRAINT. A positive body atom already implied by another positive body
% atom on the same arguments is redundant.
%   Slot0         body slot of the implying atom, of Pred0.
%   Slot1         a different body slot, of the implied atom of Pred1.
%   Pred0, Pred1  predicates with Pred0 implying Pred1.
%   pruned: h(V0) :- parent(V0,V1), ancestor(V0,V1).
%   kept:   h(V0) :- parent(V0,V1).                     the same meaning
%   kept:   h(V0) :- parent(V0,V1), ancestor(V1,V0).    different arguments
:- positive_body_literal(Slot0, _, Pred0, Arity),
    positive_body_literal(Slot1, _, Pred1, Arity),
    Slot0 != Slot1,
    implies_pred(Pred0, Pred1),
    same_term_bindings(body, Slot0, body, Slot1).

% CONSTRAINT. A plain or disjunctive head atom that a positive body atom
% already implies on the same arguments makes the clause derive nothing new.
%   Slot0        body slot of the implying atom, of Pred0.
%   Slot1, Mode  head slot and mode of the implied atom of Pred1; an
%                unconditional atom of a normal or disjunctive head.
% Here ancestor is learnable and the background already derives it from
% parent, which is why the implication is proved:
%   pruned: ancestor(V0,V1) :- parent(V0,V1).       already in the background
%   kept:   ancestor(V0,V2) :- parent(V0,V1), ancestor(V1,V2).
%   kept:   {ancestor(V0,V1)} :- parent(V0,V1).     choice heads are not pruned
:- positive_body_literal(Slot0, _, Pred0, Arity),
    head_literal(Slot1, Mode, Pred1, Arity),
    plain_disjunctive_head_mode(Mode),
    implies_pred(Pred0, Pred1),
    same_term_bindings(body, Slot0, head, Slot1).

% CONSTRAINT. A positive body atom together with the negation of what it
% implies, on the same arguments, makes the body unsatisfiable.
%   Slot0  body slot of the positive atom, of Pred0.
%   Slot1  a different body slot, of the negated atom of Pred1.
%   pruned: h(V0) :- parent(V0,V1), not ancestor(V0,V1).
%   kept:   h(V0) :- ancestor(V0,V1), not parent(V0,V1).   the converse is fine
:- positive_body_literal(Slot0, _, Pred0, Arity),
    negative_body_literal(Slot1, _, Pred1, Arity),
    Slot0 != Slot1,
    implies_pred(Pred0, Pred1),
    same_term_bindings(body, Slot0, body, Slot1).
