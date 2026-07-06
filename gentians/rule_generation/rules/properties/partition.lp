% Closed-world partition property.
%
% Python emits partition_pred(Part,Pred) for each predicate Pred in a partition
% Part where exactly one member predicate is true for a tuple. This file prunes
% sets of negated partition members that deny the whole partition and prunes
% positive/negative contradictions inside the same partition.
%
% Shared atom shapes used here:
% - partition_pred(Part,Pred): property fact. Part is partition id; Pred is one
%   member predicate id.
% - negative_body_literal(Slot,Mode,Pred,Arity): selected negated body atom.
% - positive_body_literal(Slot,Mode,Pred,Arity): selected positive body atom.
% - same_vars(body,Slot0,body,Slot1): same tuple variables.

#defined partition_pred/2.

% Rule: Anchor negative literal has a matching negative literal for Pred in Part.
% Part is partition id. Anchor is a negative body slot whose predicate is in
% Part. Pred is another partition member. Slot is a negative literal for Pred
% with same Arity and same variable tuple as Anchor.
partition_neg_has(Part,Anchor,Pred):-
    negative_body_literal(Anchor,_,AnchorPred,Arity),
    negative_body_literal(Slot,_,Pred,Arity),
    partition_pred(Part,AnchorPred),
    partition_pred(Part,Pred),
    same_vars(body,Anchor,body,Slot).

% Rule: Anchor is missing a negated member of its partition.
% Part is partition id. Anchor is a negative literal in Part. Pred ranges over
% all predicates in Part. If no matching negative literal exists for some Pred,
% the partition is not fully denied.
partition_neg_missing(Part,Anchor):-
    negative_body_literal(Anchor,_,AnchorPred,_),
    partition_pred(Part,AnchorPred),
    partition_pred(Part,Pred),
    not partition_neg_has(Part,Anchor,Pred).

% Constraint: reject complete denial of one partition for same tuple.
% Anchor is a negative body literal in Part. If no partition_neg_missing exists,
% every member predicate of Part is negated on the same variables. Since exactly
% one partition member must hold, the body is impossible.
:- negative_body_literal(Anchor,_,AnchorPred,_),
    partition_pred(Part,AnchorPred),
    not partition_neg_missing(Part,Anchor).

% Constraint: reject positive member plus negative member of same partition tuple.
% PosSlot is positive PosPred tuple. NegSlot is not NegPred same tuple. If both
% predicates are in Part, the positive member already excludes other members and
% makes the negative redundant or contradictory depending on member identity.
:- positive_body_literal(PosSlot,_,PosPred,Arity),
    negative_body_literal(NegSlot,_,NegPred,Arity),
    partition_pred(Part,PosPred),
    partition_pred(Part,NegPred),
    same_vars(body,PosSlot,body,NegSlot).
