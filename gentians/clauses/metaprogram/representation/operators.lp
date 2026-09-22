% Operator classifications and normalized relations over selected variables.
% Python emits generic_* for every operator, including its specialized families.
% lt_vars/leq_vars orient >/>= in reverse; neq and distinctness are symmetric.
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

arithmetic_mode(Mode):- generic_arithmetic_mode(Mode).

comparison_mode(Mode):- generic_comparison_mode(Mode).

simple_comparison_mode(Mode):- neq_comparison_mode(Mode).

simple_comparison_mode(Mode):- eq_comparison_mode(Mode).

simple_comparison_mode(Mode):- less_than_comparison_mode(Mode).

simple_comparison_mode(Mode):- greater_than_comparison_mode(Mode).

simple_comparison_mode(Mode):- leq_comparison_mode(Mode).

simple_comparison_mode(Mode):- geq_comparison_mode(Mode).

strict_comparison_available:- less_than_comparison_mode(_).

strict_comparison_available:- greater_than_comparison_mode(_).

lt_vars(Left,Right):-
    selected(body,Slot,Mode),
    less_than_comparison_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right).

lt_vars(Right,Left):-
    selected(body,Slot,Mode),
    greater_than_comparison_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right).

leq_vars(Left,Right):-
    selected(body,Slot,Mode),
    leq_comparison_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right).

leq_vars(Right,Left):-
    selected(body,Slot,Mode),
    geq_comparison_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right).

neq_vars(Left,Right):-
    selected(body,Slot,Mode),
    neq_comparison_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right).

neq_vars(Right,Left):- neq_vars(Left,Right).

known_distinct_vars(Left,Right):- neq_vars(Left,Right).

known_distinct_vars(Left,Right):- lt_vars(Left,Right).

known_distinct_vars(Right,Left):- known_distinct_vars(Left,Right).
