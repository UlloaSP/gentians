% Closed-world implication property.
%
% Python emits implies_pred(Pred0,Pred1) when Pred0(X...) implies Pred1(X...)
% for same-arity predicates. Equivalent predicates are treated as implications
% too. This file prunes body/head/negative literals made redundant or impossible
% by a positive body literal.
%
% Shared atom shapes used here:
% - implies_pred(Pred0,Pred1): property fact. Pred0 implies Pred1.
% - equivalent_pair(Pred0,Pred1): symmetric alias from equivalent.lp.
% - implies_or_equivalent(Pred0,Pred1): local union alias.
% - positive_body_literal/4, negative_body_literal/4, head_literal/4: selected
%   literal aliases.
% - same_vars(Section0,Slot0,Section1,Slot1): both literals use same tuple.

% Python fact contract:
% - implies_pred(Pred0,Pred1): emitted by Python when same-arity predicate id
%   Pred0 implies predicate id Pred1 for every observed tuple.
% Python fact detail: implies_pred(Pred0,Pred1) says Pred0 tuple truth implies Pred1 tuple truth.
#defined implies_pred/2.

% Rule: explicit implication participates in implication pruning.
% Pred0 is source predicate id. Pred1 is implied predicate id.
implies_or_equivalent(Pred0,Pred1):- implies_pred(Pred0,Pred1).

% Rule: equivalent predicates participate as implications in both directions.
% equivalent_pair/2 is already symmetric.
implies_or_equivalent(Pred0,Pred1):- equivalent_pair(Pred0,Pred1).

% Constraint: reject redundant positive body implication target.
% Slot0 is positive body Pred0 tuple. Slot1 is positive body Pred1 with same
% Arity and same variables. Since Pred0 implies Pred1, Slot1 adds no filtering.
:- positive_body_literal(Slot0,_,Pred0,Arity),
    positive_body_literal(Slot1,_,Pred1,Arity),
    Slot0 != Slot1,
    implies_or_equivalent(Pred0,Pred1),
    same_vars(body,Slot0,body,Slot1).

% Constraint: reject head literal already implied by positive body literal.
% Slot0 is positive body Pred0 tuple. Slot1 is head Pred1 same tuple. If body
% already implies head, the generated rule is tautological/redundant.
:- positive_body_literal(Slot0,_,Pred0,Arity),
    head_literal(Slot1,_,Pred1,Arity),
    implies_or_equivalent(Pred0,Pred1),
    same_vars(body,Slot0,head,Slot1).

% Constraint: reject contradiction between positive source and negative target.
% Slot0 is positive body Pred0 tuple. Slot1 is not Pred1 for same tuple. If
% Pred0 implies Pred1, the negative literal cannot hold.
:- positive_body_literal(Slot0,_,Pred0,Arity),
    negative_body_literal(Slot1,_,Pred1,Arity),
    Slot0 != Slot1,
    implies_or_equivalent(Pred0,Pred1),
    same_vars(body,Slot0,body,Slot1).
