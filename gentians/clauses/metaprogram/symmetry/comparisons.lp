% Choose the ascending variable-id orientation of a selected disequality.

:- selected(body, Slot, Mode),
    neq_comparison_mode(Mode),
    var_at(body, Slot, 0, Left),
    var_at(body, Slot, 1, Right),
    Left > Right.
