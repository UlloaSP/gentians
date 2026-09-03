% Closed-world asymmetric predicate property.
%
% Python emits asymmetric_pred(Pred) when binary predicate Pred never has both
% Pred(X,Y) and Pred(Y,X) in observed facts. Asymmetry implies irreflexivity
% and antisymmetry, so this file exports those base-property atoms instead of
% duplicating their constraints here.
%
% Shared atom shapes used here:
% - asymmetric_pred(Pred): Python property fact. Pred is a binary predicate id.
% - irreflexive_pred(Pred): derived property atom consumed by irreflexive.lp.
% - antisymmetric_pred(Pred): property atom consumed by antisymmetric.lp.
%
% Python fact contract:
% - asymmetric_pred(Pred): emitted by Python when binary predicate id Pred is
%   asymmetric in closed-world evidence.
% Python fact detail: asymmetric_pred(Pred) marks binary predicate id Pred as asymmetric.
#defined asymmetric_pred/1.

% Rule: asymmetric predicates are irreflexive.
% Pred is the predicate id. The derived irreflexive_pred(Pred) lets
% irreflexive.lp reject self-pairs Pred(Var,Var).
irreflexive_pred(Pred):- asymmetric_pred(Pred).

% Rule: asymmetric predicates are antisymmetric.
% Pred is the predicate id. The derived antisymmetric_pred(Pred) lets
% antisymmetric.lp reject reversed positive pairs Pred(X,Y), Pred(Y,X) for
% distinct variables.
antisymmetric_pred(Pred):- asymmetric_pred(Pred).
