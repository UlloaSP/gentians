% Closed-world partition property.
%
% Python emits partition_pred(Part,Pred) for each predicate Pred in a partition
% Part where exactly one member predicate is true for a tuple. This file prunes
% sets of negated partition members that deny the whole partition. Different
% members of one partition are mutex, so this file exports mutex_pred/2 instead
% of duplicating mutex pruning here.

#defined partition_pred/2.

mutex_pred(Pred0,Pred1):-
    partition_pred(Part,Pred0),
    partition_pred(Part,Pred1),
    Pred0 < Pred1.

partition_neg_has(Part,Anchor,AnchorPred):-
    negative_body_literal(Anchor,_,AnchorPred,_),
    partition_pred(Part,AnchorPred).

partition_neg_has(Part,Anchor,Pred):-
    negative_body_literal(Anchor,_,AnchorPred,Arity),
    negative_body_literal(Slot,_,Pred,Arity),
    partition_pred(Part,AnchorPred),
    partition_pred(Part,Pred),
    same_vars(body,Anchor,body,Slot).

partition_neg_missing(Part,Anchor):-
    negative_body_literal(Anchor,_,AnchorPred,_),
    partition_pred(Part,AnchorPred),
    partition_pred(Part,Pred),
    not partition_neg_has(Part,Anchor,Pred).

:- negative_body_literal(Anchor,_,AnchorPred,_),
    partition_pred(Part,AnchorPred),
    not partition_neg_missing(Part,Anchor).
