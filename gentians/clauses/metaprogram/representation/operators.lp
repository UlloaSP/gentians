% Operator classifications and normalized relations over selected variables.
% mode_kind classifies operators; comparison_operator records simple operators.
% selected_lt/selected_leq orient >/>= in reverse; neq and distinctness are symmetric.
% These predicates describe selected comparisons, not their transitive closure.

arithmetic_mode(Mode) :- mode_kind(Mode, arithmetic).

comparison_mode(Mode) :- mode_kind(Mode, comparison).

strict_comparison_available :- comparison_operator(_, lt).

strict_comparison_available :- comparison_operator(_, gt).

selected_lt(Left, Right) :-
    selected(body, Slot, Mode),
    comparison_operator(Mode, lt),
    var_at(body, Slot, 0, Left),
    var_at(body, Slot, 1, Right).

selected_lt(Right, Left) :-
    selected(body, Slot, Mode),
    comparison_operator(Mode, gt),
    var_at(body, Slot, 0, Left),
    var_at(body, Slot, 1, Right).

selected_leq(Left, Right) :-
    selected(body, Slot, Mode),
    comparison_operator(Mode, leq),
    var_at(body, Slot, 0, Left),
    var_at(body, Slot, 1, Right).

selected_leq(Right, Left) :-
    selected(body, Slot, Mode),
    comparison_operator(Mode, geq),
    var_at(body, Slot, 0, Left),
    var_at(body, Slot, 1, Right).

selected_neq(Left, Right) :-
    selected(body, Slot, Mode),
    comparison_operator(Mode, neq),
    var_at(body, Slot, 0, Left),
    var_at(body, Slot, 1, Right).

selected_neq(Right, Left) :- selected_neq(Left, Right).

known_unequal_values(Left, Right) :- selected_neq(Left, Right).

known_unequal_values(Left, Right) :- selected_lt(Left, Right).

known_unequal_values(Right, Left) :- known_unequal_values(Left, Right).
