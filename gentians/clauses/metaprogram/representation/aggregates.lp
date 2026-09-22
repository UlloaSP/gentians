% Aggregate positions are flattened: tuple, condition arguments, result.
% aggregate_condition_atom offsets start inside the condition region; add
% TupleArity to obtain a var_at position. The result is the last argument.

#defined aggregate_mode/3.
#defined aggregate_condition_atom/5.

aggregate_tuple_var(Slot,Var):-
    selected(body,Slot,Mode),
    aggregate_mode(Mode,TupleArity,_),
    Arg = 0..TupleArity-1,
    var_at(body,Slot,Arg,Var).

aggregate_condition_var(Slot,Var):-
    selected(body,Slot,Mode),
    aggregate_mode(Mode,TupleArity,_),
    mode(body,Mode,_,Arity,_),
    Arg = TupleArity..Arity-2,
    var_at(body,Slot,Arg,Var).

aggregate_result_var(Slot,Var):-
    selected(body,Slot,Mode),
    aggregate_mode(Mode,_,_),
    mode(body,Mode,_,Arity,_),
    Result = Arity-1,
    var_at(body,Slot,Result,Var).

aggregate_internal_arg(Slot,Arg):-
    selected(body,Slot,Mode),
    aggregate_mode(Mode,_,_),
    mode(body,Mode,_,Arity,_),
    Arg = 0..Arity-2.

aggregate_internal_position(body,Slot,Arg):- aggregate_internal_arg(Slot,Arg).

aggregate_condition_arg(Slot,Pred,LocalArg,Var):-
    selected(body,Slot,Mode),
    aggregate_mode(Mode,TupleArity,_),
    aggregate_condition_atom(Mode,_,Pred,Offset,Arity),
    LocalArg = 0..Arity-1,
    Arg = TupleArity + Offset + LocalArg,
    var_at(body,Slot,Arg,Var).
