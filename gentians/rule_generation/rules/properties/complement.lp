% Closed-world complement predicate property.
%
% Python emits complement_pred(Pred0,Pred1) when same-arity predicates are
% logical complements. Complements are also mutex, so this file exports
% mutex_pred/2 and keeps the complement-specific double-negative constraint.
%
% Shared atom shapes used here:
% - complement_pred(Pred0,Pred1): property fact.
% - complement_pair(Pred0,Pred1): local symmetric alias.
% - mutex_pred(Pred0,Pred1): derived property atom consumed by mutex.lp.
% - negative_body_literal(Slot,Mode,Pred,Arity): selected negated body literal.
% - same_vars(body,Slot0,body,Slot1): both literals use same tuple.

% Python fact contract:
% - complement_pred(Pred0,Pred1): emitted by Python when same-arity predicate ids
%   Pred0 and Pred1 are logical complements in closed-world evidence.
% Python fact detail: complement_pred(Pred0,Pred1) marks same-arity predicates Pred0 and Pred1 as complements.
#defined complement_pred/2.

% Rule: preserve declared complement direction.
% Pred0 and Pred1 are predicate ids known to be complements.
complement_pair(Pred0,Pred1):- complement_pred(Pred0,Pred1).

% Rule: add reverse complement direction.
% Complement relation is symmetric for pruning queries.
complement_pair(Pred1,Pred0):- complement_pred(Pred0,Pred1).

% Rule: complements are mutex in the declared direction.
% Pred0 and Pred1 are predicate ids. mutex.lp owns positive mutex pruning.
mutex_pred(Pred0,Pred1):- complement_pred(Pred0,Pred1).

% Rule: complements are mutex in the reverse direction.
% The reverse derived atom makes complement-derived mutex facts explicit.
mutex_pred(Pred1,Pred0):- complement_pred(Pred0,Pred1).

% Constraint: reject pair of negated complements with same variables.
% Slot0 and Slot1 are ordered negative body literals with same Arity. Pred0 and
% Pred1 are complements. same_vars proves both are applied to same tuple.
:- negative_body_literal(Slot0,_,Pred0,Arity),
    negative_body_literal(Slot1,_,Pred1,Arity),
    Slot0 < Slot1,
    complement_pair(Pred0,Pred1),
    same_vars(body,Slot0,body,Slot1).
