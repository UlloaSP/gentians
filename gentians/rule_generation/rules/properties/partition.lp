% Closed-world partition property.
%
% Python emits partition_pred(Part,Pred) for each predicate Pred in a partition
% Part where exactly one member predicate is true for a tuple. This file prunes
% sets of negated partition members that deny the whole partition. Different
% members of one partition are mutex, so this file exports mutex_pred/2 instead
% of duplicating mutex pruning here.
%
% Shared atom shapes used here:
% - partition_pred(Part,Pred): property fact. Part is partition id; Pred is one
%   member predicate id.
% - mutex_pred(Pred0,Pred1): derived property atom consumed by mutex.lp.
% - negative_body_literal(Slot,Mode,Pred,Arity): selected negated body atom.
% - same_vars(body,Slot0,body,Slot1): same tuple variables.

% Python fact contract:
% - partition_pred(Part,Pred): emitted by Python for every predicate id Pred in
%   closed-world partition id Part, where exactly one member is true per tuple.
% Python fact detail: partition_pred(Part,Pred) lists predicate id Pred as member of partition Part.
#defined partition_pred/2.

% Rule: distinct members of one partition are mutex.
% Part is the partition id. Pred0 and Pred1 are different predicate ids in that
% partition. Pred0 < Pred1 emits one canonical direction; mutex.lp adds the
% reverse direction and owns the positive/negative mutex constraints.
mutex_pred(Pred0,Pred1):-
    partition_pred(Part,Pred0),
    partition_pred(Part,Pred1),
    Pred0 < Pred1.

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
