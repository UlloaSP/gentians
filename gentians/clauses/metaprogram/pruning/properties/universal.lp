% A universal predicate holds for every tuple of the product of its argument
% values (see domains.lp). A positive literal is redundant when other positive
% literals bind every argument inside that product; its negation is then
% impossible.
%   same(a,a). same(a,b). same(b,a). same(b,b). n(a). n(b). n(c).
%   h(X) :- same(X,Y), n(Y), not same(Y,X).   pruned: X, Y come from same's product
%   h(X) :- n(X), n(Y), not same(X,Y).         kept: c lies outside the product


:- positive_body_literal(Slot, _, Pred, _),
    universal_pred(Pred),
    not domain_literal_uncovered_elsewhere(universal(Pred), Slot).

:- negative_body_literal(Slot, _, Pred, _),
    universal_pred(Pred),
    not domain_literal_uncovered(universal(Pred), Slot).
