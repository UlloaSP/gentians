% Choose the ascending variable-id orientation of a symmetric comparison whose
% operands may swap: X != Y and X = Y mean Y != X and Y = X. Operands with
% different types, directions or labels are not interchangeable: with
% b(V0), a(V1) and var(a)!=var(b), V1!=V0 is the only legal orientation.
%   kept:   V0!=V1   V0=V1        pruned: V1!=V0   V1=V0

symmetric_comparison(Mode) :- comparison_operator(Mode, neq).
symmetric_comparison(Mode) :- comparison_operator(Mode, eq).

:- selected(body, Slot, Mode),
    symmetric_comparison(Mode),
    interchangeable_operands(Mode),
    var_at(body, Slot, 0, Left),
    var_at(body, Slot, 1, Right),
    Left > Right.
