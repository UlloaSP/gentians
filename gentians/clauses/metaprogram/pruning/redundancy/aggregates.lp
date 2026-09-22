% Remove key-determined tuple discriminators only if a shorter template exists.
% Reject repeated aggregate computations with different result ids. The key
% check uses the existing predicate-level projection of condition arguments.

#defined aggregate_mode/3.
#defined aggregate_has_shorter_mode/1.
#defined count_aggregate_mode/1.
#defined sum_aggregate_mode/1.
#defined key_pred/2.
#defined key_arg/2.

aggregate_key_input_missing(Slot, Pred, Key) :-
    key_arg(Key, Input),
    aggregate_condition_arg(Slot, Pred, Input, InputVar),
    not aggregate_tuple_var(Slot, InputVar).

aggregate_input_differs(Slot0, Slot1) :-
    selected(body, Slot0, Mode),
    selected(body, Slot1, Mode),
    aggregate_mode(Mode, _, _),
    Slot1 = Slot0 + 1,
    aggregate_internal_arg(Slot0, Arg),
    var_at(body, Slot0, Arg, Left),
    var_at(body, Slot1, Arg, Right),
    Left != Right.

same_aggregate_inputs(Slot0, Slot1) :-
    selected(body, Slot0, Mode),
    selected(body, Slot1, Mode),
    aggregate_mode(Mode, _, _),
    Slot1 = Slot0 + 1,
    not aggregate_input_differs(Slot0, Slot1).

:- same_aggregate_inputs(Slot0, Slot1),
    aggregate_result_var(Slot0, Result0),
    aggregate_result_var(Slot1, Result1),
    Result0 != Result1.

:- selected(body, Slot, Mode), aggregate_has_shorter_mode(Mode),
    aggregate_tuple_binding(Slot, Position, OutputVariable), Position > 0,
    aggregate_condition_arg(Slot, Predicate, Output, OutputVariable),
    key_pred(Predicate, Key), not key_arg(Key, Output),
    not aggregate_key_input_missing(Slot, Predicate, Key).
