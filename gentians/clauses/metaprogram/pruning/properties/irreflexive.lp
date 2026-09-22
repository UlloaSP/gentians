% Closed-world irreflexive predicate property.
%
% This file owns irreflexive knowledge: reject positive self-pairs Pred(Var, Var)
% and export the equivalent argument-distinct property for binary predicates.
% Stronger properties such as asymmetric, acyclic, and strict_order derive
% irreflexive_pred(Pred) in their own files.

arg_distinct_pred(Pred, 0, 1) :- irreflexive_pred(Pred).

:- positive_body_literal(Slot, _, Pred, 2),
    irreflexive_pred(Pred),
    var_at(body, Slot, 0, Var),
    var_at(body, Slot, 1, Var).
