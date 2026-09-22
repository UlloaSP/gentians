% Closed-world argument equality property.
%
% Python emits arg_equal_pred(Pred, Arg0, Arg1) when every true tuple of predicate
% Pred has equal values at argument positions Arg0 and Arg1. The enumerator
% chooses identical variable ids at these positions. This is an identification
% policy: equal values alone do not imply that distinct ids are inconsistent.


:- selected(Section, Slot, Mode),
    normal_literal(Section, Slot, Mode, Pred, _),
    arg_equal_pred(Pred, Arg0, Arg1),
    var_at(Section, Slot, Arg0, Var0),
    var_at(Section, Slot, Arg1, Var1),
    Var0 != Var1.

:- selected(body, Slot, Mode),
    aggregate_condition_atom(Mode, _, Pred, _),
    arg_equal_pred(Pred, LocalArg0, LocalArg1),
    aggregate_condition_arg(Slot, Pred, LocalArg0, Var0),
    aggregate_condition_arg(Slot, Pred, LocalArg1, Var1),
    Var0 != Var1.
