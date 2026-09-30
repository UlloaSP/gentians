% Closed-world asymmetric predicate property.
%
% Python emits asymmetric_pred(Pred) when binary predicate Pred never has both
% Pred(X, Y) and Pred(Y, X) in observed facts. Asymmetry implies irreflexivity
% and antisymmetry, so this file exports those base-property atoms instead of
% duplicating their constraints here.


% DEFINITION, reusable property bridge. irreflexive_pred(Pred): Pred never
% relates a value to itself.
%   Pred  signed predicate id of a binary closed predicate proved asymmetric.
% Pred(X,X) would be its own reverse, which asymmetry forbids. The self-pair
% check is owned by pruning/properties/irreflexive.lp.
irreflexive_pred(Pred) :- asymmetric_pred(Pred).

% DEFINITION, reusable property bridge. antisymmetric_pred(Pred): Pred never
% holds in both directions for two different values.
%   Pred  signed predicate id of a binary closed predicate proved asymmetric.
% The reversed-pair check is owned by pruning/properties/antisymmetric.lp.
antisymmetric_pred(Pred) :- asymmetric_pred(Pred).
