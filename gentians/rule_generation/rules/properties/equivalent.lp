% Closed-world equivalent predicate property.
%
% Python emits equivalent_pred(Pred0,Pred1) when two predicates with same arity
% have identical truth values for same argument tuple. This file rejects clauses
% that contain both equivalent literals with identical variables in same section.
%
% Shared atom shapes used here:
% - equivalent_pred(Pred0,Pred1): property fact. Pred0 implies Pred1 and Pred1
%   implies Pred0.
% - equivalent_pair(Pred0,Pred1): local symmetric alias.
% - normal_literal(Section,Slot,Mode,Pred,Arity): selected normal literal.
% - same_vars(Section,Slot0,Section,Slot1): both literals use same tuple.

% Python fact contract:
% - equivalent_pred(Pred0,Pred1): emitted by Python when same-arity predicate ids
%   Pred0 and Pred1 have identical closed-world truth sets.
% Python fact detail: equivalent_pred(Pred0,Pred1) marks same-arity predicates as having identical truth sets.
#defined equivalent_pred/2.

% Rule: preserve declared equivalent direction.
% Pred0 and Pred1 are predicate ids known equivalent.
equivalent_pair(Pred0,Pred1):- equivalent_pred(Pred0,Pred1).

% Rule: add reverse equivalent direction.
% Equivalent predicates are symmetric, so downstream modules can query either
% equivalent_pair(Pred0,Pred1) or equivalent_pair(Pred1,Pred0).
equivalent_pair(Pred1,Pred0):- equivalent_pred(Pred0,Pred1).

% Constraint: reject duplicate equivalent literals in same section.
% Section is head or body. Slot0 and Slot1 are ordered selected normal literals
% with same Arity. Pred0 and Pred1 are equivalent. same_vars proves both
% literals use same variable tuple, so one of them is redundant.
:- normal_literal(Section,Slot0,_,Pred0,Arity),
    normal_literal(Section,Slot1,_,Pred1,Arity),
    Slot0 < Slot1,
    equivalent_pred(Pred0,Pred1),
    same_vars(Section,Slot0,Section,Slot1).
