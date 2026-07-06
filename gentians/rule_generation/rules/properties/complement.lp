% Closed-world complement predicate property.
%
% Python emits complement_pred(Pred0,Pred1) when same-arity predicates are
% logical complements. This file rejects two negated complement literals over
% same variables, because not Pred0(X) and not Pred1(X) cannot both hold when
% exactly one of Pred0/Pred1 holds.
%
% Shared atom shapes used here:
% - complement_pred(Pred0,Pred1): property fact.
% - complement_pair(Pred0,Pred1): local symmetric alias.
% - negative_body_literal(Slot,Mode,Pred,Arity): selected negated body literal.
% - same_vars(body,Slot0,body,Slot1): both literals use same tuple.

#defined complement_pred/2.

% Rule: preserve declared complement direction.
% Pred0 and Pred1 are predicate ids known to be complements.
complement_pair(Pred0,Pred1):- complement_pred(Pred0,Pred1).

% Rule: add reverse complement direction.
% Complement relation is symmetric for pruning queries.
complement_pair(Pred1,Pred0):- complement_pred(Pred0,Pred1).

% Constraint: reject pair of negated complements with same variables.
% Slot0 and Slot1 are ordered negative body literals with same Arity. Pred0 and
% Pred1 are complements. same_vars proves both are applied to same tuple.
:- negative_body_literal(Slot0,_,Pred0,Arity),
    negative_body_literal(Slot1,_,Pred1,Arity),
    Slot0 < Slot1,
    complement_pair(Pred0,Pred1),
    same_vars(body,Slot0,body,Slot1).
