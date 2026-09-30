% A universal predicate holds for every tuple of the product of its argument
% values (see domains.lp). A positive literal is redundant when other positive
% literals bind every argument inside that product; its negation is then
% impossible.
%   same(a,a). same(a,b). same(b,a). same(b,b). n(a). n(b). n(c).
%   h(X) :- same(X,Y), n(Y), not same(Y,X).   pruned: X, Y come from same's product
%   h(X) :- n(X), n(Y), not same(X,Y).         kept: c lies outside the product


% CONSTRAINT. A positive body atom of a universal predicate is redundant when
% every one of its arguments is a variable that a different positive atom
% binds inside the predicate's product: the atom is then always true.
%   Slot  body slot of the positive atom.
%   Pred  its predicate, universal.
% With the facts of the file header and k(a). k(b). as another predicate
% whose values lie inside the product:
%   pruned: h(V0) :- k(V0), k(V1), same(V0,V1).
%   kept:   h(V0) :- same(V0,V1).               nothing else binds V0 and V1
%   kept:   h(V0) :- n(V0), n(V1), same(V0,V1).   n reaches c; same filters it
:- positive_body_literal(Slot, _, Pred, _),
    universal_pred(Pred),
    not domain_literal_uncovered_elsewhere(universal(Pred), Slot).

% CONSTRAINT. A negated body atom of a universal predicate is impossible when
% every one of its arguments is a variable that a positive atom binds inside
% the predicate's product.
%   Slot  body slot of the negated atom.
%   Pred  its predicate, universal.
%   pruned and kept: see the two examples in the file header.
:- negative_body_literal(Slot, _, Pred, _),
    universal_pred(Pred),
    not domain_literal_uncovered(universal(Pred), Slot).
