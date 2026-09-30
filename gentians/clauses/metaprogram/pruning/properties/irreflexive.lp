% Closed-world irreflexive predicate property.
%
% This file owns irreflexive knowledge: reject positive self-pairs Pred(Var, Var)
% and export the equivalent argument-distinct property for binary predicates.
% Stronger properties such as asymmetric, acyclic, and strict_order derive
% irreflexive_pred(Pred) in their own files.

% DEFINITION, reusable property bridge. arg_distinct_pred(Pred, 0, 1): the two
% arguments of an irreflexive binary predicate always differ.
%   Pred  signed predicate id of an irreflexive binary predicate.
%   0, 1  its two argument positions.
% Lets pruning/properties/arg_distinct.lp apply its checks (negated atoms and
% aggregate conditions) without repeating them here.
arg_distinct_pred(Pred, 0, 1) :- irreflexive_pred(Pred).

% CONSTRAINT. A positive body atom of an irreflexive predicate may not relate
% a variable to itself: it could never be true.
%   Slot  body slot of the positive binary atom.
%   Pred  its predicate, irreflexive.
%   Var   the single variable id written at both arguments.
% With before/2 irreflexive:
%   pruned: h(V0) :- before(V0,V0).
%   kept:   h(V0) :- before(V0,V1).
:- positive_body_literal(Slot, _, Pred, 2),
    irreflexive_pred(Pred),
    var_at(body, Slot, 0, Var),
    var_at(body, Slot, 1, Var).
