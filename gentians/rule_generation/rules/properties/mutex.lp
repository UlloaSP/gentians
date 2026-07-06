% Closed-world mutex predicate property.
%
% Python emits mutex_pred(Pred0,Pred1) when same-arity predicates cannot both be
% true for the same tuple. Complements are also mutex. This file prunes
% impossible positive pairs and redundant positive/negative pairs.
%
% Shared atom shapes used here:
% - mutex_pred(Pred0,Pred1): property fact.
% - complement_pair(Pred0,Pred1): complement alias from complement.lp.
% - mutex_pair(Pred0,Pred1): local symmetric/derived alias.
% - positive_body_literal/4 and negative_body_literal/4: selected body atoms.
% - same_vars(body,Slot0,body,Slot1): both literals use same tuple.

#defined mutex_pred/2.

% Rule: preserve declared mutex direction.
% Pred0 and Pred1 are predicate ids that cannot co-occur on same tuple.
mutex_pair(Pred0,Pred1):- mutex_pred(Pred0,Pred1).

% Rule: add reverse mutex direction.
% Mutex relation is symmetric for pruning.
mutex_pair(Pred1,Pred0):- mutex_pred(Pred0,Pred1).

% Rule: complements are mutex.
% If Pred0 complements Pred1, they cannot both be true for same tuple.
mutex_pair(Pred0,Pred1):- complement_pair(Pred0,Pred1).

% Constraint: reject impossible positive mutex pair.
% Slot0 and Slot1 are ordered positive body literals with same Arity. same_vars
% proves they target same tuple. mutex_pair says they cannot both be true.
:- positive_body_literal(Slot0,_,Pred0,Arity),
    positive_body_literal(Slot1,_,Pred1,Arity),
    Slot0 < Slot1,
    mutex_pair(Pred0,Pred1),
    same_vars(body,Slot0,body,Slot1).

% Constraint: reject redundant positive plus negative mutex pair.
% If Pred0(X) is positive and Pred1 is mutex with Pred0, then not Pred1(X) is
% already implied and should not be generated as an extra body literal.
:- positive_body_literal(Slot0,_,Pred0,Arity),
    negative_body_literal(Slot1,_,Pred1,Arity),
    Slot0 != Slot1,
    mutex_pair(Pred0,Pred1),
    same_vars(body,Slot0,body,Slot1).
