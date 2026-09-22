% Closed-world strict order predicate property.
%
% Python emits strict_order_pred(Pred) when binary predicate Pred behaves like a
% strict order in observed facts. A strict order is acyclic and transitive.
% Acyclic predicates already derive irreflexive and antisymmetric atoms, so this
% file does not duplicate those bridge rules.

#defined strict_order_pred/1.

transitive_pred(Pred):- strict_order_pred(Pred).

acyclic_pred(Pred):- strict_order_pred(Pred).
