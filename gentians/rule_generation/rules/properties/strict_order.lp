% Closed-world strict order predicate property.
%
% Python emits strict_order_pred(Pred) when binary predicate Pred behaves like a
% strict order in observed facts. A strict order is irreflexive, antisymmetric,
% transitive, and acyclic, so this file exports those base-property atoms and
% keeps the corresponding pruning in the target property files.
%
% Shared atom shapes used here:
% - strict_order_pred(Pred): Python property fact for a binary predicate id.
% - irreflexive_pred(Pred): derived property atom consumed by irreflexive.lp.
% - antisymmetric_pred(Pred): derived property atom consumed by antisymmetric.lp.
% - transitive_pred(Pred): property atom consumed by transitive.lp.
% - acyclic_pred(Pred): property atom consumed by acyclic.lp.
%
% Python fact contract:
% - strict_order_pred(Pred): emitted by Python when binary predicate id Pred is
%   a strict order in closed-world evidence.
% Python fact detail: strict_order_pred(Pred) marks binary predicate id Pred as strict order.
#defined strict_order_pred/1.

% Rule: strict orders are irreflexive.
% Pred is the predicate id. The derived atom delegates self-pair pruning to
% irreflexive.lp.
irreflexive_pred(Pred):- strict_order_pred(Pred).

% Rule: strict orders are antisymmetric.
% Pred is the predicate id. The derived atom delegates reversed-pair pruning to
% antisymmetric.lp.
antisymmetric_pred(Pred):- strict_order_pred(Pred).

% Rule: strict orders are transitive.
% Pred is the predicate id. The derived atom delegates transitive closure
% redundancy and contradiction pruning to transitive.lp.
transitive_pred(Pred):- strict_order_pred(Pred).

% Rule: strict orders are acyclic.
% Pred is the predicate id. The derived atom delegates explicit cycle pruning
% to acyclic.lp.
acyclic_pred(Pred):- strict_order_pred(Pred).
