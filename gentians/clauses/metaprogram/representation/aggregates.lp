% Translate flattened placeholders into tuple, condition and result roles.
% The compiler supplies static role-to-position mappings.
% Condition identifies an occurrence; Predicate alone does not.


aggregate_tuple_binding(Slot, Position, Variable) :-
    selected(body, Slot, Mode), mode_aggregate_tuple_arg(Mode, Position, FlatPosition),
    var_at(body, Slot, FlatPosition, Variable).

aggregate_tuple_var(Slot, Variable) :- aggregate_tuple_binding(Slot, _, Variable).

aggregate_condition_position(Slot, Position, Variable) :-
    selected(body, Slot, Mode),
    mode_aggregate_condition_arg(Mode, _, _, Position),
    var_at(body, Slot, Position, Variable).

aggregate_condition_var(Slot, Variable) :- aggregate_condition_position(Slot, _, Variable).

aggregate_condition_binding(Slot, Condition, Position, Variable) :-
    selected(body, Slot, Mode),
    mode_aggregate_condition_arg(Mode, Condition, Position, FlatPosition),
    var_at(body, Slot, FlatPosition, Variable).

aggregate_condition_arg(Slot, Predicate, Position, Variable) :-
    selected(body, Slot, Mode),
    aggregate_condition_atom(Mode, Condition, Predicate, _),
    aggregate_condition_binding(Slot, Condition, Position, Variable).

aggregate_result_var(Slot, Variable) :-
    selected(body, Slot, Mode), mode_aggregate_result_arg(Mode, Position),
    var_at(body, Slot, Position, Variable).

aggregate_internal_arg(Slot, Position) :-
    selected(body, Slot, Mode), mode_aggregate_tuple_arg(Mode, _, Position).

aggregate_internal_arg(Slot, Position) :-
    selected(body, Slot, Mode),
    mode_aggregate_condition_arg(Mode, _, _, Position).

aggregate_internal_position(body, Slot, Position) :- aggregate_internal_arg(Slot, Position).

aggregate_element_tuple_binding(Slot, Element, Position, Variable) :-
    selected(body, Slot, Mode),
    mode_aggregate_element_tuple_arg(Mode, Element, Position, FlatPosition),
    var_at(body, Slot, FlatPosition, Variable).

aggregate_element_tuple_var(Slot, Element, Variable) :-
    aggregate_element_tuple_binding(Slot, Element, _, Variable).

aggregate_element_condition_binding(Slot, Element, Condition, Argument, Variable) :-
    selected(body, Slot, Mode),
    mode_aggregate_element_condition_arg(Mode, Element, Condition, Argument, FlatPosition),
    var_at(body, Slot, FlatPosition, Variable).

aggregate_element_condition_var(Slot, Element, Variable) :-
    aggregate_element_condition_binding(Slot, Element, _, _, Variable).

aggregate_element_arg(Slot, Element, Position) :-
    selected(body, Slot, Mode),
    mode_aggregate_element_tuple_arg(Mode, Element, _, Position).

aggregate_element_arg(Slot, Element, Position) :-
    selected(body, Slot, Mode),
    mode_aggregate_element_condition_arg(Mode, Element, _, _, Position).

aggregate_internal_arg(Slot, Position) :- aggregate_element_arg(Slot, _, Position).

aggregate_output_var(Slot, Variable) :-
    selected(body, Slot, Mode), mode_aggregate_output_arg(Mode, Position),
    var_at(body, Slot, Position, Variable).

aggregate_guard_var(Slot, Variable) :-
    selected(body, Slot, Mode), mode_aggregate_guard_arg(Mode, Position),
    var_at(body, Slot, Position, Variable).
