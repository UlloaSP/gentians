% Exceeding a predicate cardinality cap is impossible only when all selected
% positive tuples are provably pairwise distinct. Different variable names alone
% do not establish distinct ground values.

#defined cardinality_upper_pred/2.

positive_body_tuple_known_distinct(Pred, Slot0, Slot1) :-
    positive_body_literal(Slot0, _, Pred, Arity),
    positive_body_literal(Slot1, _, Pred, Arity),
    Slot0 < Slot1,
    Arg = 0..Arity-1,
    var_at(body, Slot0, Arg, Left),
    var_at(body, Slot1, Arg, Right),
    known_unequal_values(Left, Right).

cardinality_upper_not_pairwise_distinct(Pred) :-
    positive_body_literal(Slot0, _, Pred, Arity),
    positive_body_literal(Slot1, _, Pred, Arity),
    Slot0 < Slot1,
    not positive_body_tuple_known_distinct(Pred, Slot0, Slot1).

positive_body_cardinality(Pred, Count) :-
    cardinality_upper_pred(Pred, _),
    Count = #count{Slot : positive_body_literal(Slot, _, Pred, _)}.

:- cardinality_upper_pred(Pred, Upper),
    positive_body_cardinality(Pred, Count),
    Count > Upper,
    not cardinality_upper_not_pairwise_distinct(Pred).
