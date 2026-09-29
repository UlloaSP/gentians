% Closed-world argument equality property.
%
% Python emits arg_equal_pred(Pred, Arg0, Arg1) when every true tuple of predicate
% Pred has equal values at argument positions Arg0 and Arg1. The enumerator
% chooses identical variable ids at these positions of positive literals, which
% can only be true for equal values. A negated literal with distinct ids is not
% equivalent: not same(X,Y) holds for every X != Y.


:- positive_body_literal(Slot, _, Pred, _),
    arg_equal_pred(Pred, Arg0, Arg1),
    var_at(body, Slot, Arg0, Var0),
    var_at(body, Slot, Arg1, Var1),
    Var0 != Var1.

:- selected(body, Slot, Mode),
    aggregate_condition_atom(Mode, Condition, Pred, _),
    arg_equal_pred(Pred, LocalArg0, LocalArg1),
    aggregate_condition_arg(Slot, Condition, Pred, LocalArg0, Var0),
    aggregate_condition_arg(Slot, Condition, Pred, LocalArg1, Var1),
    Var0 != Var1.
