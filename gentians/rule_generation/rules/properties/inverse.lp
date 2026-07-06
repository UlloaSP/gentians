% Closed-world inverse predicate property.
%
% Python emits inverse_pred(Pred0,Pred1) when two binary predicates are inverses:
% Pred0(X,Y) has same truth value as Pred1(Y,X). This file removes redundant
% positive inverse pairs and contradictory positive/negative inverse pairs.
%
% Shared atom shapes used here:
% - inverse_pred(Pred0,Pred1): property fact for inverse predicate ids.
% - inverse_pair(Pred0,Pred1): local symmetric alias.
% - positive_body_literal(Slot,Mode,Pred,2): positive binary body literal.
% - negative_body_literal(Slot,Mode,Pred,2): negative binary body literal.
% - reversed_binary_vars(body,Slot0,body,Slot1): Slot0 uses X,Y and Slot1 uses
%   Y,X.

#defined inverse_pred/2.

% Rule: preserve declared inverse direction.
% Pred0 and Pred1 are binary predicate ids.
inverse_pair(Pred0,Pred1):- inverse_pred(Pred0,Pred1).

% Rule: add reverse inverse direction.
% If Pred0 is inverse of Pred1, Pred1 is inverse of Pred0.
inverse_pair(Pred1,Pred0):- inverse_pred(Pred0,Pred1).

% Constraint: reject redundant positive inverse pair.
% Slot0 and Slot1 are ordered positive binary body literals. Pred0/Pred1 are
% inverse predicates. reversed_binary_vars proves they use opposite variables,
% so both literals express same fact.
:- positive_body_literal(Slot0,_,Pred0,2),
    positive_body_literal(Slot1,_,Pred1,2),
    Slot0 < Slot1,
    inverse_pair(Pred0,Pred1),
    reversed_binary_vars(body,Slot0,body,Slot1).

% Constraint: reject contradiction between positive and negative inverse facts.
% Positive Pred0(X,Y) and negative Pred1(Y,X) cannot both be useful because
% inverse_pair says they have same truth value.
:- positive_body_literal(Slot0,_,Pred0,2),
    negative_body_literal(Slot1,_,Pred1,2),
    inverse_pair(Pred0,Pred1),
    reversed_binary_vars(body,Slot0,body,Slot1).
