% A sign-known addition already entails the selected operand/result comparison:
% with Rt > 0, R = L + Rt entails L < R and L <= R; with Rt >= 0 it entails
% L <= R. Signs come from inference/numeric.lp.
%
% In the examples n/1 is a closed predicate whose argument is proved > 0 and
% z/1 one whose argument is proved >= 0.

% CONSTRAINT. With Right > 0, "Left < Result" repeats what the addition says.
%   Slot    body slot of "Left + Right = Result".
%   Left    left operand.
%   Right   right operand, proved > 0.
%   Result  the sum, explicitly compared as Left < Result.
%   pruned: n(V1), V0+V1=V2, V0 < V2.
%   kept:   n(V1), V0+V1=V2.
%   kept:   V0+V1=V2, V0 < V2 without sign evidence for V1: it is informative
:- addition(Slot, Left, Right, Result),
    positive_value(Right),
    selected_lt(Left, Result).

% CONSTRAINT. The mirror image: with Left > 0, "Right < Result" is entailed.
%   Left    left operand, proved > 0.
%   Result  the sum, explicitly compared as Right < Result.
%   pruned: n(V0), V0+V1=V2, V1 < V2.
%   kept:   n(V0), V0+V1=V2.
:- addition(Slot, Left, Right, Result),
    positive_value(Left),
    selected_lt(Right, Result).

% CONSTRAINT. With Right >= 0, "Left <= Result" is entailed.
%   Right   right operand, proved >= 0.
%   Result  the sum, explicitly compared as Left <= Result.
%   pruned: z(V1), V0+V1=V2, V0 <= V2.
%   kept:   z(V1), V0+V1=V2, V0 < V2.       strict: V1 could be 0
:- addition(Slot, Left, Right, Result),
    nonnegative_value(Right),
    selected_leq(Left, Result).

% CONSTRAINT. The mirror image: with Left >= 0, "Right <= Result" is entailed.
%   Left    left operand, proved >= 0.
%   Result  the sum, explicitly compared as Right <= Result.
%   pruned: z(V0), V0+V1=V2, V1 <= V2.
%   kept:   z(V0), V0+V1=V2, V1 < V2.
:- addition(Slot, Left, Right, Result),
    nonnegative_value(Left),
    selected_leq(Right, Result).
