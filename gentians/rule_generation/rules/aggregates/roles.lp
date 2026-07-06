% Aggregate argument roles.
%
% Aggregate modes are rendered by Python as
%   #function{TupleVars : ConditionAtoms}=Result
% Their mode argument tuple is flattened as:
%   tuple variables, then all condition atom variables, then result variable.
% This file names those regions so safety and pruning modules can reason about
% aggregate internals without duplicating offset arithmetic.
%
% Shared atom shapes used here:
% - aggregate_mode(Mode,TupleArity,AtomCount): Python fact. Mode is aggregate
%   mode id; TupleArity is number of grouped tuple variables; AtomCount is
%   number of condition atoms.
% - aggregate_condition_atom(Mode,AtomIndex,Pred,Offset,Arity): Python fact.
%   Pred is condition predicate id; Offset is start index in flattened condition
%   variables; Arity is that condition atom's arity.
% - selected(body,Slot,Mode): aggregate literals only appear in body.
% - mode(body,Mode,Pred,Arity,Recall): Arity is flattened aggregate arity.
% - var_at(body,Slot,Arg,Var): variable assignment for aggregate argument Arg.

#defined aggregate_mode/3.
#defined aggregate_condition_atom/5.

% Rule: variables in aggregate tuple/grouping positions.
% Slot is aggregate body slot. Var occurs at Arg in the prefix 0..TupleArity-1.
% These variables appear before the colon in rendered aggregate syntax.
aggregate_tuple_var(Slot,Var):-
    selected(body,Slot,Mode),
    aggregate_mode(Mode,TupleArity,_),
    Arg = 0..TupleArity-1,
    var_at(body,Slot,Arg,Var).

% Rule: variables in aggregate condition atom positions.
% Slot is aggregate body slot. TupleArity gives prefix length. Arity is total
% flattened mode arity. Arg ranges from first condition variable to Arity-2,
% because Arity-1 is the result variable.
aggregate_condition_var(Slot,Var):-
    selected(body,Slot,Mode),
    aggregate_mode(Mode,TupleArity,_),
    mode(body,Mode,_,Arity,_),
    Arg = TupleArity..Arity-2,
    var_at(body,Slot,Arg,Var).

% Rule: variable holding aggregate result.
% Slot is aggregate body slot. Result is Arity-1, the final flattened argument.
% Var renders after the equals sign in #count{...}=Var.
aggregate_result_var(Slot,Var):-
    selected(body,Slot,Mode),
    aggregate_mode(Mode,_,_),
    mode(body,Mode,_,Arity,_),
    Result = Arity-1,
    var_at(body,Slot,Result,Var).

% Rule: internal aggregate argument positions.
% Arg ranges over all tuple and condition arguments, excluding result Arity-1.
% Used when comparing aggregate inputs independently from their result variable.
aggregate_internal_arg(Slot,Arg):-
    selected(body,Slot,Mode),
    aggregate_mode(Mode,_,_),
    mode(body,Mode,_,Arity,_),
    Arg = 0..Arity-2.

% Rule: map flattened condition variables back to predicate/local arguments.
% Slot is aggregate body slot. Pred is the condition predicate id. LocalArg is
% the argument index inside that condition atom. Var is the variable assigned
% to the flattened position TupleArity + Offset + LocalArg.
aggregate_condition_arg(Slot,Pred,LocalArg,Var):-
    selected(body,Slot,Mode),
    aggregate_mode(Mode,TupleArity,_),
    aggregate_condition_atom(Mode,_,Pred,Offset,Arity),
    LocalArg = 0..Arity-1,
    Arg = TupleArity + Offset + LocalArg,
    var_at(body,Slot,Arg,Var).

% Rule: aggregate results are considered safe.
% Var is result of an aggregate selected in the body. This mirrors ASP behavior:
% #count{...}=Var binds Var when the aggregate literal is in the body. Separate
% constraints still require the result to be consumed elsewhere.
safe_var(Var):- aggregate_result_var(_,Var).
