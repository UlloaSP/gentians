% Closed-world equivalent predicate property.
%
% Python emits equivalent_pred(Pred0, Pred1) when two predicates with same arity
% have identical truth values for same argument tuple. Equivalence is
% implication in both directions, so this file exports implies_pred/2. It keeps
% only equivalent-specific duplicate pruning that implication cannot express:
% duplicate negated body literals. Head predicates are learned, so no property
% fact ever names them.


equivalent_pair(Pred0, Pred1) :- equivalent_pred(Pred0, Pred1).

equivalent_pair(Pred1, Pred0) :- equivalent_pred(Pred0, Pred1).

implies_pred(Pred0, Pred1) :- equivalent_pred(Pred0, Pred1).

implies_pred(Pred1, Pred0) :- equivalent_pred(Pred0, Pred1).

:- negative_body_literal(Slot0, _, Pred0, Arity),
    negative_body_literal(Slot1, _, Pred1, Arity),
    Slot0 < Slot1,
    equivalent_pair(Pred0, Pred1),
    same_term_bindings(body, Slot0, body, Slot1).
