% Closed-world argument distinctness property.
%
% Python emits arg_distinct_pred(Pred, Arg0, Arg1) when every true tuple of
% predicate Pred has different values at positions Arg0 and Arg1. Other
% property files may derive arg_distinct_pred/3 when they imply it; for example
% irreflexive.lp derives arg_distinct_pred(Pred, 0, 1) for binary predicates.
% This file rejects generated literals that assign the same variable to those
% positions.

#defined arg_distinct_pred/3.
#defined aggregate_condition_atom/5.

arg_distinct_self_pair_owned_by_irreflexive(Slot, Mode, Pred) :-
    positive_body_literal(Slot, Mode, Pred, 2),
    irreflexive_pred(Pred).

:- selected(Section, Slot, Mode),
    normal_literal(Section, Slot, Mode, Pred, _),
    arg_distinct_pred(Pred, Arg0, Arg1),
    var_at(Section, Slot, Arg0, Var),
    var_at(Section, Slot, Arg1, Var),
    not arg_distinct_self_pair_owned_by_irreflexive(Slot, Mode, Pred).

:- selected(body, Slot, Mode),
    aggregate_condition_atom(Mode, _, Pred, Offset, _),
    arg_distinct_pred(Pred, LocalArg0, LocalArg1),
    aggregate_condition_arg(Slot, Pred, LocalArg0, Var),
    aggregate_condition_arg(Slot, Pred, LocalArg1, Var).
