% Exclude self comparisons and opposite non-strict edges.
% The latter force equal values, not identical variable ids; this preserves the
% existing variable-identification policy rather than asserting inconsistency.

:- selected(body, Slot, Mode),
    simple_comparison_mode(Mode),
    var_at(body, Slot, 0, Var),
    var_at(body, Slot, 1, Var).

:- selected_leq(Left, Right), selected_leq(Right, Left).
