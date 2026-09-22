% Reject strict self comparisons and strict/non-strict reverse pairs.
% Strict/strict reverse pairs are covered by the cycle check in numeric.lp.

:- selected(body, Slot, Mode),
    strict_comparison_args(Mode, LeftArg, RightArg),
    var_at(body, Slot, LeftArg, Var),
    var_at(body, Slot, RightArg, Var).

:- selected_lt(Left, Right), selected_leq(Right, Left).
