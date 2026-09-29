% A sign-known addition already entails the selected operand/result comparison:
% with Rt > 0, R = L + Rt entails L < R and L <= R; with Rt >= 0 it entails
% L <= R. Signs come from inference/numeric.lp.

:- addition(Slot, Left, Right, Result),
    positive_value(Right),
    selected_lt(Left, Result).

:- addition(Slot, Left, Right, Result),
    positive_value(Left),
    selected_lt(Right, Result).

:- addition(Slot, Left, Right, Result),
    nonnegative_value(Right),
    selected_leq(Left, Result).

:- addition(Slot, Left, Right, Result),
    nonnegative_value(Left),
    selected_leq(Right, Result).
