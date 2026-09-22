% Translate flattened placeholders into tuple, condition and result roles.
% Only this file knows the tuple/condition/result storage offsets.
% Condition identifies an occurrence; Predicate alone does not.

#defined aggregate_mode/3.
#defined aggregate_condition_atom/5.

aggregate_tuple_binding(Slot, Position, Variable) :-
    selected(body, Slot, Mode), aggregate_mode(Mode, TupleArity, _),
    Position = 0..TupleArity-1, var_at(body, Slot, Position, Variable).

aggregate_tuple_var(Slot, Variable) :- aggregate_tuple_binding(Slot, _, Variable).

aggregate_condition_position(Slot, Position, Variable) :-
    selected(body, Slot, Mode), aggregate_mode(Mode, TupleArity, _),
    mode(body, Mode, _, Arity, _), Position = TupleArity..Arity-2,
    var_at(body, Slot, Position, Variable).

aggregate_condition_var(Slot, Variable) :- aggregate_condition_position(Slot, _, Variable).

aggregate_condition_binding(Slot, Condition, Position, Variable) :-
    selected(body, Slot, Mode), aggregate_mode(Mode, TupleArity, _),
    aggregate_condition_atom(Mode, Condition, _, Offset, Arity),
    Position = 0..Arity-1, FlatPosition = TupleArity + Offset + Position,
    var_at(body, Slot, FlatPosition, Variable).

aggregate_condition_arg(Slot, Predicate, Position, Variable) :-
    selected(body, Slot, Mode),
    aggregate_condition_atom(Mode, Condition, Predicate, _, _),
    aggregate_condition_binding(Slot, Condition, Position, Variable).

aggregate_result_var(Slot, Variable) :-
    selected(body, Slot, Mode), aggregate_mode(Mode, _, _),
    mode(body, Mode, _, Arity, _), var_at(body, Slot, Arity-1, Variable).

aggregate_internal_arg(Slot, Position) :-
    selected(body, Slot, Mode), aggregate_mode(Mode, _, _),
    mode(body, Mode, _, Arity, _), Position = 0..Arity-2.

aggregate_internal_position(body, Slot, Position) :- aggregate_internal_arg(Slot, Position).
