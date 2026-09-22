% Order count tuples and eligible full-local condition permutations.
% The one-condition template must cover exactly the tuple; sum permutations
% keep the weight fixed. Global variables cannot be exchanged.

#defined count_aggregate_mode/1.
#defined sum_aggregate_mode/1.

:- selected(body, Slot, Mode), count_aggregate_mode(Mode),
    aggregate_tuple_binding(Slot, First, Left),
    aggregate_tuple_binding(Slot, Second, Right), First < Second, Left > Right.

full_local_condition(Slot, Mode) :-
    selected(body, Slot, Mode), aggregate_mode(Mode, Arity, 1),
    aggregate_condition_atom(Mode, 0, _, _, Arity),
    not condition_has_non_tuple_variable(Slot),
    not aggregate_tuple_has_global_variable(Slot).

condition_has_non_tuple_variable(Slot) :-
    aggregate_condition_binding(Slot, 0, _, Variable),
    not aggregate_tuple_var(Slot, Variable).

aggregate_tuple_has_global_variable(Slot) :-
    aggregate_tuple_var(Slot, Variable), global_context_var(Variable).

count_condition_orderable(Slot) :-
    full_local_condition(Slot, Mode), count_aggregate_mode(Mode).

sum_condition_orderable(Slot, Weight) :-
    full_local_condition(Slot, Mode), sum_aggregate_mode(Mode),
    aggregate_tuple_binding(Slot, 0, Weight).

:- count_condition_orderable(Slot),
    aggregate_condition_binding(Slot, 0, First, Left),
    aggregate_condition_binding(Slot, 0, Second, Right), First < Second, Left > Right.

:- sum_condition_orderable(Slot, Weight),
    aggregate_condition_binding(Slot, 0, First, Left),
    aggregate_condition_binding(Slot, 0, Second, Right), First < Second,
    Left != Weight, Right != Weight, Left > Right.
