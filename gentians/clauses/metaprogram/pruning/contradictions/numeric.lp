% Reject impossible arithmetic/order combinations under the per-argument sign
% evidence of inference/numeric.lp. Inferred strict-order cycles are impossible.
% Each rule requires the sign of exactly the operand that makes it impossible:
%   R = L + Rt, R < L   needs Rt >= 0 (R = A - B can be negative otherwise)
%   R = L \ D, D <= R   needs D > 0
%   R = L * Rt, R < L   needs L > 0 and Rt > 0
%   R = L / Rt, L < R   needs L >= 0 and Rt > 0
%
% In the examples below n/1 is a closed predicate whose argument is proved
% > 0 (positive_arg) and z/1 one whose argument is proved >= 0
% (nonnegative_arg); "..." stands for the rest of an otherwise legal clause.

% This cycle check also covers opposite selected strict comparisons and
% strict reversals of the operand/result order inferred from positive addition.
% CONSTRAINT. The entailed strict order may not contain a cycle: no variable
% can be strictly below itself.
%   Var  a variable id on a cycle of inferred_lt.
%   pruned: ..., V0 < V1, V1 < V0.                  opposite comparisons
%   pruned: ..., V0 < V1, V1 < V2, V2 < V0.         a longer cycle
%   pruned: n(V1), V0+V1=V2, V2 < V0.               V0 < V2 is inferred
%   kept:   ..., V0 < V1, V1 < V2.
:- inferred_lt(Var, Var).

% CONSTRAINT. With Right >= 0, the sum Left + Right cannot be below Left.
%   Slot    body slot of "Left + Right = Result".
%   Left    left operand.
%   Right   right operand, proved >= 0.
%   Result  the sum, explicitly compared as Result < Left.
%   pruned: z(V1), V0+V1=V2, V2 < V0.
%   kept:   V0+V1=V2, V2 < V0 without sign evidence for V1 (V1 may be negative)
:- addition(Slot, Left, Right, Result),
    nonnegative_value(Right),
    selected_lt(Result, Left).

% CONSTRAINT. The mirror image: with Left >= 0, the sum cannot be below Right.
%   Left    left operand, proved >= 0.
%   Right   right operand.
%   Result  the sum, explicitly compared as Result < Right.
%   pruned: z(V0), V0+V1=V2, V2 < V1.
%   kept:   V0+V1=V2, V2 < V1 without sign evidence for V0
:- addition(Slot, Left, Right, Result),
    nonnegative_value(Left),
    selected_lt(Result, Right).

% CONSTRAINT. With Right > 0, the sum Left + Right cannot be below or equal
% to Left.
%   Right   right operand, proved > 0.
%   Result  the sum, explicitly compared as Result <= Left.
%   pruned: n(V1), V0+V1=V2, V2 <= V0.
%   kept:   z(V1), V0+V1=V2, V2 <= V0.      V1 = 0 makes V2 = V0 possible
:- addition(Slot, Left, Right, Result),
    positive_value(Right),
    selected_leq(Result, Left).

% CONSTRAINT. The mirror image: with Left > 0, the sum cannot be below or
% equal to Right.
%   Left    left operand, proved > 0.
%   Result  the sum, explicitly compared as Result <= Right.
%   pruned: n(V0), V0+V1=V2, V2 <= V1.
%   kept:   z(V0), V0+V1=V2, V2 <= V1.
:- addition(Slot, Left, Right, Result),
    positive_value(Left),
    selected_leq(Result, Right).

% CONSTRAINT. A remainder is always below a positive divisor, so
% "Divisor <= Result" is impossible.
%   Slot     body slot of "Dividend \ Divisor = Result".
%   Divisor  right operand, proved > 0.
%   Result   the remainder, explicitly compared as Divisor <= Result.
%   pruned: n(V1), V0\V1=V2, V1 <= V2.
%   kept:   n(V1), V0\V1=V2, V2 < V1.
:- modulo(Slot, _, Divisor, Result),
    positive_value(Divisor),
    selected_leq(Divisor, Result).

% CONSTRAINT. A product of two positive integers cannot be below its left
% factor.
%   Left, Right  factors, both proved > 0.
%   Result       the product, explicitly compared as Result < Left.
%   pruned: n(V0), n(V1), V0*V1=V2, V2 < V0.
%   kept:   n(V0), n(V1), V0*V1=V2, V2 <= V0.    equal when V1 = 1
:- multiplication(Slot, Left, Right, Result),
    positive_value(Left),
    positive_value(Right),
    selected_lt(Result, Left).

% CONSTRAINT. The mirror image: the product cannot be below its right factor.
%   Result  the product, explicitly compared as Result < Right.
%   pruned: n(V0), n(V1), V0*V1=V2, V2 < V1.
%   kept:   n(V0), n(V1), V0*V1=V2, V2 <= V1.
:- multiplication(Slot, Left, Right, Result),
    positive_value(Left),
    positive_value(Right),
    selected_lt(Result, Right).

% CONSTRAINT. Dividing a value >= 0 by a positive integer cannot yield more
% than the value.
%   Left    dividend, proved >= 0.
%   Right   divisor, proved > 0.
%   Result  the quotient, explicitly compared as Left < Result.
%   pruned: z(V0), n(V1), V0/V1=V2, V0 < V2.
%   kept:   z(V0), n(V1), V0/V1=V2, V2 <= V0.
:- division(Slot, Left, Right, Result),
    nonnegative_value(Left),
    positive_value(Right),
    selected_lt(Left, Result).
