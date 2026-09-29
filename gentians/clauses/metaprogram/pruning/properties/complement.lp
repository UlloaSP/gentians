% Closed-world complement predicate property.
%
% Python emits complement_pred(Pred0, Pred1) when same-arity predicates are
% disjoint and their union is the product of its argument values. Complements
% are also mutex, so this file exports mutex_pred/2. Denying both is impossible
% only for a tuple inside that product (see domains.lp):
%   a(1). b(2). c(1). c(2). e(5,5).
%   h(X) :- c(X), not a(X), not b(X).       pruned: c only reaches 1 and 2
%   h(X) :- e(X,X), not a(X), not b(X).     kept: X = 5 is neither a nor b


mutex_pred(Pred0, Pred1) :- complement_pred(Pred0, Pred1).

complement_domain(Pred0, Pred1, complement(Pred0, Pred1)) :-
    complement_pred(Pred0, Pred1).

complement_domain(Pred1, Pred0, complement(Pred0, Pred1)) :-
    complement_pred(Pred0, Pred1).

:- negative_body_literal(Slot0, _, Pred0, Arity),
    negative_body_literal(Slot1, _, Pred1, Arity),
    Slot0 < Slot1,
    complement_domain(Pred0, Pred1, Domain),
    same_term_bindings(body, Slot0, body, Slot1),
    not domain_literal_uncovered(Domain, Slot0).
