% Closed-world asymmetric predicate property.
%
% Python emits asymmetric_pred(Pred) when binary predicate Pred never has both
% Pred(X, Y) and Pred(Y, X) in observed facts. Asymmetry implies irreflexivity
% and antisymmetry, so this file exports those base-property atoms instead of
% duplicating their constraints here.

#defined asymmetric_pred/1.

irreflexive_pred(Pred) :- asymmetric_pred(Pred).

antisymmetric_pred(Pred) :- asymmetric_pred(Pred).
