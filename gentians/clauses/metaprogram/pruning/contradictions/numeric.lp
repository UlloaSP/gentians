% Reject impossible arithmetic/order combinations under the per-argument sign
% evidence of inference/numeric.lp. Inferred strict-order cycles are impossible.
% Each rule requires the sign of exactly the operand that makes it impossible:
%   R = L + Rt, R < L   needs Rt >= 0 (R = A - B can be negative otherwise)
%   R = L \ D, D <= R   needs D > 0
%   R = L * Rt, R < L   needs L > 0 and Rt > 0
%   R = L / Rt, L < R   needs L >= 0 and Rt > 0

% This cycle check also covers opposite selected strict comparisons and
% strict reversals of the operand/result order inferred from positive addition.
:- inferred_lt(Var, Var).

:- addition(Slot, Left, Right, Result),
    nonnegative_value(Right),
    selected_lt(Result, Left).

:- addition(Slot, Left, Right, Result),
    nonnegative_value(Left),
    selected_lt(Result, Right).

:- addition(Slot, Left, Right, Result),
    positive_value(Right),
    selected_leq(Result, Left).

:- addition(Slot, Left, Right, Result),
    positive_value(Left),
    selected_leq(Result, Right).

:- modulo(Slot, _, Divisor, Result),
    positive_value(Divisor),
    selected_leq(Divisor, Result).

:- multiplication(Slot, Left, Right, Result),
    positive_value(Left),
    positive_value(Right),
    selected_lt(Result, Left).

:- multiplication(Slot, Left, Right, Result),
    positive_value(Left),
    positive_value(Right),
    selected_lt(Result, Right).

:- division(Slot, Left, Right, Result),
    nonnegative_value(Left),
    positive_value(Right),
    selected_lt(Left, Result).
