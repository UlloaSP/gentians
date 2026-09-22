% A universal predicate is redundant positively only when every variable remains
% bound by another positive literal. Its negation is impossible. Binary universal
% predicates also supply reflexivity for self-pair pruning.


reflexive_pred(Pred) :-
    universal_pred(Pred),
    mode_atom(_, Pred, 2).

universal_literal_missing_guard(Slot) :-
    positive_body_literal(Slot, _, Pred, _),
    universal_pred(Pred),
    var_at(body, Slot, _, Var),
    not positive_body_var_outside_slot(Slot, Var).

:- positive_body_literal(Slot, _, Pred, _),
    universal_pred(Pred),
    not universal_literal_missing_guard(Slot).

:- negative_body_literal(Slot, _, Pred, _),
    universal_pred(Pred).
