% Closed-world partition property.
%
% Python emits partition_pred(Part, Pred) for each predicate Pred in a partition
% Part where exactly one member predicate is true for each tuple of the product
% of the members' argument values. This file prunes sets of negated partition
% members that deny the whole partition for a tuple inside that product (see
% domains.lp); outside it every member can be false. Different
% members of one partition are mutex, so this file exports mutex_pred/2 instead
% of duplicating mutex pruning here.
%
% The examples assume the partition {red, green, blue}.


% DEFINITION, reusable property bridge. mutex_pred(Pred0, Pred1): two
% different members of one partition never hold for the same tuple.
%   Pred0, Pred1  signed predicate ids of two members of partition Part;
%                 "Pred0 < Pred1" states each pair once.
% The shared checks are owned by pruning/properties/mutex.lp.
mutex_pred(Pred0, Pred1) :-
    partition_pred(Part, Pred0),
    partition_pred(Part, Pred1),
    Pred0 < Pred1.

% DEFINITION, local helper. partition_neg_has(Part, Anchor, Pred): the body
% negates member Pred on the arguments of the negated atom at Anchor.
%   Part    id of a partition.
%   Anchor  body slot of a negated atom of some member of Part; its arguments
%           are the tuple being examined.
%   Pred    a member of Part negated on exactly those arguments.
% Used only, negated, by partition_neg_missing below.
% Case 1: the anchor atom itself.
partition_neg_has(Part, Anchor, AnchorPred) :-
    negative_body_literal(Anchor, _, AnchorPred, _),
    partition_pred(Part, AnchorPred).

% DEFINITION, local helper. Same predicate. Case 2: another negated atom of a
% member of Part with the same arguments as the anchor.
%   Slot  (body variable) body slot of that other negated atom.
partition_neg_has(Part, Anchor, Pred) :-
    negative_body_literal(Anchor, _, AnchorPred, Arity),
    negative_body_literal(Slot, _, Pred, Arity),
    partition_pred(Part, AnchorPred),
    partition_pred(Part, Pred),
    same_term_bindings(body, Anchor, body, Slot).

% DEFINITION, local helper. partition_neg_missing(Part, Anchor): some member
% of the partition is not negated on the anchor's arguments.
%   Part, Anchor  as above.
% Used only, negated, by the constraint below.
partition_neg_missing(Part, Anchor) :-
    negative_body_literal(Anchor, _, AnchorPred, _),
    partition_pred(Part, AnchorPred),
    partition_pred(Part, Pred),
    not partition_neg_has(Part, Anchor, Pred).

% CONSTRAINT. The body may not deny every member of a partition for a tuple
% that certainly lies in the partition's domain: exactly one member holds
% there, so the body could never be satisfied.
%   Anchor      body slot of a negated member atom.
%   AnchorPred  its predicate.
%   Part        the partition, all of whose members are negated on the
%               anchor's arguments; every argument of the anchor must be a
%               variable bound inside the domain by a positive atom.
% With node(V0) binding V0 inside the partition's domain:
%   pruned: :- node(V0), not red(V0), not green(V0), not blue(V0).
%   kept:   :- node(V0), not red(V0), not green(V0).      blue remains possible
%   kept:   :- w(V0), not red(V0), not green(V0), not blue(V0).
%           when w can reach values outside the domain
:- negative_body_literal(Anchor, _, AnchorPred, _),
    partition_pred(Part, AnchorPred),
    not partition_neg_missing(Part, Anchor),
    not domain_literal_uncovered(partition(Part), Anchor).
