% Closed-world strict order predicate property.
%
% Python emits strict_order_pred(Pred) when binary predicate Pred behaves like a
% strict order in observed facts. A strict order is acyclic and transitive.
% Acyclic predicates already derive irreflexive and antisymmetric atoms, so this
% file does not duplicate those bridge rules.
%
% This file has no constraint of its own.


% DEFINITION, reusable property bridge. transitive_pred(Pred): Pred(X,Y) and
% Pred(Y,Z) entail Pred(X,Z).
%   Pred  signed predicate id of a binary closed predicate proved a strict
%         order.
% The shortcut checks are owned by pruning/properties/transitive.lp.
transitive_pred(Pred) :- strict_order_pred(Pred).

% DEFINITION, reusable property bridge. acyclic_pred(Pred): Pred has no
% directed cycle.
%   Pred  signed predicate id of a binary closed predicate proved a strict
%         order.
% The cycle checks are owned by pruning/properties/acyclic.lp, which in turn
% derives irreflexive_pred and antisymmetric_pred.
acyclic_pred(Pred) :- strict_order_pred(Pred).
