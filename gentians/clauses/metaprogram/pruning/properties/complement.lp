% Closed-world complement predicate property.
%
% Python emits complement_pred(Pred0, Pred1) when same-arity predicates are
% disjoint and their union is the product of its argument values. Complements
% are also mutex, so this file exports mutex_pred/2. Denying both is impossible
% only for a tuple inside that product (see domains.lp):
%   a(1). b(2). c(1). c(2). e(5,5).
%   h(X) :- c(X), not a(X), not b(X).       pruned: c only reaches 1 and 2
%   h(X) :- e(X,X), not a(X), not b(X).     kept: X = 5 is neither a nor b


% DEFINITION, reusable property bridge. mutex_pred(Pred0, Pred1): the two
% predicates never hold for the same tuple.
%   Pred0, Pred1  signed predicate ids of a complement pair.
% Complements are disjoint by definition. The shared checks (both positive,
% or one positive and the other negated) are owned by
% pruning/properties/mutex.lp.
mutex_pred(Pred0, Pred1) :- complement_pred(Pred0, Pred1).

% DEFINITION, local helper. complement_domain(Pred0, Pred1, Domain): the
% domain over which two predicates are complementary, available for either
% order of the pair.
%   Pred0, Pred1  the two predicates, in the order the constraint meets them.
%   Domain        the term complement(A, B), with A and B in the order Python
%                 emitted; domain_cover/4 facts refer to that exact term.
% Used only by the constraint below.
% Case 1: the pair in the emitted order.
complement_domain(Pred0, Pred1, complement(Pred0, Pred1)) :-
    complement_pred(Pred0, Pred1).

% DEFINITION, local helper. Same predicate. Case 2: the pair reversed; the
% Domain term keeps the emitted order.
complement_domain(Pred1, Pred0, complement(Pred0, Pred1)) :-
    complement_pred(Pred0, Pred1).

% CONSTRAINT. Both members of a complement pair may not be denied for the
% same tuple when that tuple certainly lies in their shared domain: one of
% the two holds there, so the body could never be satisfied.
%   Slot0 < Slot1  body slots of the two negated atoms, with identical
%                  arguments.
%   Pred0, Pred1   a complement pair.
%   Domain         their shared domain; every argument of the atom at Slot0
%                  must be a variable bound inside it by a positive atom.
%   pruned and kept: see the example in the file header.
:- negative_body_literal(Slot0, _, Pred0, Arity),
    negative_body_literal(Slot1, _, Pred1, Arity),
    Slot0 < Slot1,
    complement_domain(Pred0, Pred1, Domain),
    same_term_bindings(body, Slot0, body, Slot1),
    not domain_literal_uncovered(Domain, Slot0).
