% Exceeding a predicate cardinality cap is impossible only when all selected
% positive tuples are provably pairwise distinct. Different variable names alone
% do not establish distinct ground values.


% DEFINITION, local helper. positive_body_tuple_known_distinct(Pred, Slot0,
% Slot1): two positive atoms of Pred certainly denote different tuples.
%   Pred           the predicate of both atoms, one with a cardinality cap;
%                  nothing is derived for predicates without one.
%   Slot0 < Slot1  their body slots.
% It holds when, at some argument position, the two atoms hold variables the
% clause proves unequal (known_unequal_values: an explicit "!=" or "<").
% Used only, negated, by the next rule.
positive_body_tuple_known_distinct(Pred, Slot0, Slot1) :-
    cardinality_upper_pred(Pred, _),
    positive_body_literal(Slot0, _, Pred, Arity),
    positive_body_literal(Slot1, _, Pred, Arity),
    Slot0 < Slot1,
    Arg = 0..Arity-1,
    var_at(body, Slot0, Arg, Left),
    var_at(body, Slot1, Arg, Right),
    known_unequal_values(Left, Right).

% DEFINITION, local helper. cardinality_upper_not_pairwise_distinct(Pred):
% some two positive atoms of Pred might denote the same tuple.
%   Pred  a predicate with two positive body atoms not proved distinct.
% Used only, negated, by the constraint below.
cardinality_upper_not_pairwise_distinct(Pred) :-
    cardinality_upper_pred(Pred, _),
    positive_body_literal(Slot0, _, Pred, Arity),
    positive_body_literal(Slot1, _, Pred, Arity),
    Slot0 < Slot1,
    not positive_body_tuple_known_distinct(Pred, Slot0, Slot1).

% DEFINITION, local helper. positive_body_cardinality(Pred, Count): how many
% positive body atoms of Pred the clause has.
%   Pred   a predicate with a proved cardinality cap.
%   Count  number of body slots holding a positive atom of Pred.
% Used only by the constraint below.
positive_body_cardinality(Pred, Count) :-
    cardinality_upper_pred(Pred, _),
    Count = #count{Slot : positive_body_literal(Slot, _, Pred, _)}.

% CONSTRAINT. The body may not require more provably different tuples of a
% predicate than the predicate can have.
%   Pred   the predicate.
%   Upper  its proved maximum number of tuples.
%   Count  its positive body atoms, all pairwise proved distinct.
% With cardinality_upper_pred(root,1):
%   pruned: :- root(V0), root(V1), V0 != V1.    two different roots cannot exist
%   kept:   :- root(V0), root(V1), e(V0,V1).    V0 and V1 may be the same root
:- cardinality_upper_pred(Pred, Upper),
    positive_body_cardinality(Pred, Count),
    Count > Upper,
    not cardinality_upper_not_pairwise_distinct(Pred).
