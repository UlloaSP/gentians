% Operator classifications and normalized relations over selected variables.
% Python emits generic_* for every operator, including its specialized families.
% selected_lt/selected_leq orient >/>= in reverse; neq and distinctness are symmetric.
% These predicates describe selected comparisons, not their transitive closure.

#defined generic_arithmetic_mode/1.
#defined neq_comparison_mode/1.
#defined eq_comparison_mode/1.
#defined less_than_comparison_mode/1.
#defined greater_than_comparison_mode/1.
#defined leq_comparison_mode/1.
#defined geq_comparison_mode/1.
#defined generic_comparison_mode/1.
#defined strict_comparison_args/3.

arithmetic_mode(Mode) :- generic_arithmetic_mode(Mode).

comparison_mode(Mode) :- generic_comparison_mode(Mode).

simple_comparison_mode(Mode) :- neq_comparison_mode(Mode).

simple_comparison_mode(Mode) :- eq_comparison_mode(Mode).

simple_comparison_mode(Mode) :- less_than_comparison_mode(Mode).

simple_comparison_mode(Mode) :- greater_than_comparison_mode(Mode).

simple_comparison_mode(Mode) :- leq_comparison_mode(Mode).

simple_comparison_mode(Mode) :- geq_comparison_mode(Mode).

strict_comparison_available :- less_than_comparison_mode(_).

strict_comparison_available :- greater_than_comparison_mode(_).

selected_lt(Left, Right) :-
    selected(body, Slot, Mode),
    less_than_comparison_mode(Mode),
    var_at(body, Slot, 0, Left),
    var_at(body, Slot, 1, Right).

selected_lt(Right, Left) :-
    selected(body, Slot, Mode),
    greater_than_comparison_mode(Mode),
    var_at(body, Slot, 0, Left),
    var_at(body, Slot, 1, Right).

selected_leq(Left, Right) :-
    selected(body, Slot, Mode),
    leq_comparison_mode(Mode),
    var_at(body, Slot, 0, Left),
    var_at(body, Slot, 1, Right).

selected_leq(Right, Left) :-
    selected(body, Slot, Mode),
    geq_comparison_mode(Mode),
    var_at(body, Slot, 0, Left),
    var_at(body, Slot, 1, Right).

selected_neq(Left, Right) :-
    selected(body, Slot, Mode),
    neq_comparison_mode(Mode),
    var_at(body, Slot, 0, Left),
    var_at(body, Slot, 1, Right).

selected_neq(Right, Left) :- selected_neq(Left, Right).

known_unequal_values(Left, Right) :- selected_neq(Left, Right).

known_unequal_values(Left, Right) :- selected_lt(Left, Right).

known_unequal_values(Right, Left) :- known_unequal_values(Left, Right).
