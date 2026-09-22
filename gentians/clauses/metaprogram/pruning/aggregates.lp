% Canonicalize aggregate tuples and reject duplicate computations.
% Full-local count conditions can permute all tuple variables; sums keep their
% weight fixed. Key-determined tuple discriminators are removed only when the
% bias provides a shorter aggregate template. Equal-mode duplicate checks use
% adjacent slots because slot ordering makes equal inputs contiguous.

#defined aggregate_mode/3.
#defined aggregate_has_shorter_mode/1.
#defined count_aggregate_mode/1.
#defined sum_aggregate_mode/1.
#defined key_pred/2.
#defined key_arg/2.

:- selected(body,Slot,Mode),
    aggregate_mode(Mode,TupleArity,_),
    A0 = 0..TupleArity-1,
    A1 = 0..TupleArity-1,
    A0 < A1,
    var_at(body,Slot,A0,Var),
    var_at(body,Slot,A1,Var).

:- selected(body,Slot,Mode),
    count_aggregate_mode(Mode),
    aggregate_mode(Mode,TupleArity,_),
    A0 = 0..TupleArity-1,
    A1 = 0..TupleArity-1,
    A0 < A1,
    var_at(body,Slot,A0,Left),
    var_at(body,Slot,A1,Right),
    Left > Right.

% Full-local condition permutations must not exchange clause-global variables.

count_full_local_condition(Slot,Mode,Offset,Arity):-
    selected(body,Slot,Mode),
    count_aggregate_mode(Mode),
    aggregate_mode(Mode,Arity,1),
    aggregate_condition_atom(Mode,0,_,Offset,Arity),
    not condition_arg_not_tuple_var(Slot,Mode,Offset,Arity),
    not count_tuple_var_used_outside(Slot).

condition_arg_not_tuple_var(Slot,Mode,Offset,Arity):-
    selected(body,Slot,Mode),
    aggregate_condition_atom(Mode,0,_,Offset,Arity),
    LocalArg = 0..Arity-1,
    Arg = Arity + Offset + LocalArg,
    var_at(body,Slot,Arg,Var),
    not aggregate_tuple_var(Slot,Var).

count_tuple_var_used_outside(Slot):-
    aggregate_tuple_var(Slot,Var),
    global_context_var(Var).

full_local_sum_condition(Slot,Mode,Offset,Arity,Weight):-
    selected(body,Slot,Mode),
    sum_aggregate_mode(Mode),
    aggregate_mode(Mode,Arity,1),
    aggregate_condition_atom(Mode,0,_,Offset,Arity),
    var_at(body,Slot,0,Weight),
    not condition_arg_not_tuple_var(Slot,Mode,Offset,Arity),
    not count_tuple_var_used_outside(Slot).

% A shorter declared tuple is valid only if all key inputs remain in the tuple.

aggregate_key_input_missing(Slot,Pred,Key):-
    key_arg(Key,Input),
    aggregate_condition_arg(Slot,Pred,Input,InputVar),
    not aggregate_tuple_var(Slot,InputVar).

:- count_full_local_condition(Slot,Mode,Offset,Arity),
    LocalArg0 = 0..Arity-1,
    LocalArg1 = 0..Arity-1,
    LocalArg0 < LocalArg1,
    Arg0 = Arity + Offset + LocalArg0,
    Arg1 = Arity + Offset + LocalArg1,
    var_at(body,Slot,Arg0,Left),
    var_at(body,Slot,Arg1,Right),
    Left > Right.

:- full_local_sum_condition(Slot,Mode,Offset,Arity,Weight),
    LocalArg0 = 0..Arity-1,
    LocalArg1 = 0..Arity-1,
    LocalArg0 < LocalArg1,
    Arg0 = Arity + Offset + LocalArg0,
    Arg1 = Arity + Offset + LocalArg1,
    var_at(body,Slot,Arg0,Left),
    var_at(body,Slot,Arg1,Right),
    Left != Weight,
    Right != Weight,
    Left > Right.

:- selected(body,Slot,Mode),
    aggregate_has_shorter_mode(Mode),
    aggregate_mode(Mode,TupleArity,_),
    TupleArg = 1..TupleArity-1,
    var_at(body,Slot,TupleArg,OutputVar),
    aggregate_condition_arg(Slot,Pred,Output,OutputVar),
    key_pred(Pred,Key),
    not key_arg(Key,Output),
    not aggregate_key_input_missing(Slot,Pred,Key).

:- selected(body,Slot,Mode),
    aggregate_mode(Mode,TupleArity,_),
    mode(body,Mode,_,Arity,_),
    A0 = TupleArity..Arity-2,
    A1 = TupleArity..Arity-2,
    A0 < A1,
    var_at(body,Slot,A0,Var),
    var_at(body,Slot,A1,Var).

% Duplicate computations compare inputs separately from their result variable.

aggregate_input_differs(Slot0,Slot1):-
    selected(body,Slot0,Mode),
    selected(body,Slot1,Mode),
    aggregate_mode(Mode,_,_),
    Slot1 = Slot0 + 1,
    aggregate_internal_arg(Slot0,Arg),
    var_at(body,Slot0,Arg,Left),
    var_at(body,Slot1,Arg,Right),
    Left != Right.

same_aggregate_inputs(Slot0,Slot1):-
    selected(body,Slot0,Mode),
    selected(body,Slot1,Mode),
    aggregate_mode(Mode,_,_),
    Slot1 = Slot0 + 1,
    not aggregate_input_differs(Slot0,Slot1).

:- same_aggregate_inputs(Slot0,Slot1),
    aggregate_result_var(Slot0,Result0),
    aggregate_result_var(Slot1,Result1),
    Result0 != Result1.
