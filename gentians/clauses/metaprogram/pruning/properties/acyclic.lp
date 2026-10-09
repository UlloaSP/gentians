% Acyclic relations exclude self-pairs, reversed pairs and positive triangles.
% The first two checks are delegated to irreflexive/antisymmetric properties.
% A negated back-edge over a positive two-step path is redundant.


% DEFINITION, reusable property bridge. irreflexive_pred(Pred): Pred never
% relates a value to itself.
%   Pred  signed predicate id of a binary closed predicate proved acyclic.
% An acyclic relation has no cycle of length 1. Deriving the base property
% lets pruning/properties/irreflexive.lp own the self-pair check instead of
% repeating it here.
irreflexive_pred(Pred) :- acyclic_pred(Pred).

% DEFINITION, reusable property bridge. antisymmetric_pred(Pred): Pred never
% holds in both directions for two different values.
%   Pred  signed predicate id of a binary closed predicate proved acyclic.
% An acyclic relation has no cycle of length 2. The reversed-pair check is
% owned by pruning/properties/antisymmetric.lp.
antisymmetric_pred(Pred) :- acyclic_pred(Pred).

% CONSTRAINT. Three positive atoms of an acyclic predicate may not form a
% triangle: the body could never be satisfied.
%   Slot0 < Slot1 < Slot2  body slots of the three atoms.
%   Pred                   the acyclic binary predicate.
%   X, Y, Z                variable ids with X->Y, Y->Z and Z->X.
% With before/2 acyclic:
%   pruned: :- before(V0,V1), before(V1,V2), before(V2,V0).
%   kept:   :- before(V0,V1), before(V1,V2).
:- positive_body_literal(Slot0, _, Pred, 2),
    positive_body_literal(Slot1, _, Pred, 2),
    positive_body_literal(Slot2, _, Pred, 2),
    Slot0 < Slot1,
    Slot1 < Slot2,
    positive_body_capacity(Pred, Capacity), Capacity >= 3,
    acyclic_pred(Pred),
    var_at(body, Slot0, 0, X),
    var_at(body, Slot0, 1, Y),
    var_at(body, Slot1, 0, Y),
    var_at(body, Slot1, 1, Z),
    var_at(body, Slot2, 0, Z),
    var_at(body, Slot2, 1, X).

% CONSTRAINT. After a positive two-step path X->Y->Z of an acyclic predicate,
% the negated back-edge "not Pred(Z,X)" is always true and therefore
% redundant.
%   Slot0, Slot1  body slots of the two positive atoms of the path.
%   Slot2         body slot of the negated atom.
%   X, Y, Z       variable ids of the path.
% With before/2 acyclic:
%   pruned: :- before(V0,V1), before(V1,V2), not before(V2,V0).
%   kept:   :- before(V0,V1), before(V1,V2), not before(V0,V2).   not a back-edge
:- positive_body_literal(Slot0, _, Pred, 2),
    positive_body_literal(Slot1, _, Pred, 2),
    negative_body_literal(Slot2, _, Pred, 2),
    acyclic_pred(Pred),
    var_at(body, Slot0, 0, X),
    var_at(body, Slot0, 1, Y),
    var_at(body, Slot1, 0, Y),
    var_at(body, Slot1, 1, Z),
    var_at(body, Slot2, 0, Z),
    var_at(body, Slot2, 1, X).
