% Input/output dataflow for normal modes and built-in body literals.

#defined mode_arg_direction/3.

directed_mode(Mode):- mode_arg_direction(Mode,_,input), not conditional_mode(Mode,_,_).
directed_mode(Mode):- mode_arg_direction(Mode,_,output), not conditional_mode(Mode,_,_).
input_count(Mode,Count):-
    directed_mode(Mode),
    Count = #count{Arg : mode_arg_direction(Mode,Arg,input)}.

bound_var(Var):-
    selected(head,Slot,Mode),
    not conditional_mode(Mode,_,_),
    mode_arg_direction(Mode,Arg,input),
    var_at(head,Slot,Arg,Var).

% A head output unified with a head input is already supplied by the caller.
produced_var(Var):-
    selected(head,Slot,Mode),
    not conditional_mode(Mode,_,_),
    mode_arg_direction(Mode,Arg,input),
    var_at(head,Slot,Arg,Var).

ready_literal(Slot):-
    selected(body,Slot,Mode),
    input_count(Mode,Count),
    Count = #count{
        Arg,Var : mode_arg_direction(Mode,Arg,input),
                  var_at(body,Slot,Arg,Var),
                  bound_var(Var)
    }.

bound_var(Var):-
    ready_literal(Slot),
    selected(body,Slot,Mode),
    positive_mode(Mode),
    mode_arg_direction(Mode,Arg,output),
    var_at(body,Slot,Arg,Var).

bound_var(Var):-
    ready_literal(Slot),
    selected(body,Slot,Mode),
    positive_mode(Mode),
    mode_arg_direction(Mode,Arg,any),
    var_at(body,Slot,Arg,Var).

bound_var(Var):-
    selected(body,Slot,Mode),
    positive_mode(Mode),
    not directed_mode(Mode),
    mode_arg_direction(Mode,Arg,any),
    var_at(body,Slot,Arg,Var).

produced_var(Var):-
    ready_literal(Slot),
    selected(body,Slot,Mode),
    positive_mode(Mode),
    mode_arg_direction(Mode,Arg,output),
    var_at(body,Slot,Arg,Var).

% Aggregate conditions own local variables. Evaluation binds its result.
bound_var(Var):- aggregate_result_var(_,Var).
produced_var(Var):- aggregate_result_var(_,Var).

% Arithmetic consumes two bound operands and produces its result.
ready_arithmetic(Slot):-
    selected(body,Slot,Mode),
    arithmetic_mode(Mode),
    var_at(body,Slot,0,Left),
    var_at(body,Slot,1,Right),
    bound_var(Left),
    bound_var(Right).

bound_var(Result):-
    ready_arithmetic(Slot),
    var_at(body,Slot,2,Result).

produced_var(Result):-
    ready_arithmetic(Slot),
    var_at(body,Slot,2,Result).

:- selected(body,Slot,Mode), arithmetic_mode(Mode), not ready_arithmetic(Slot).

% Comparisons consume bound values and produce nothing.
:- selected(body,Slot,Mode),
    comparison_mode(Mode),
    var_at(body,Slot,Arg,Var),
    not mode_arg_direction(Mode,Arg,output),
    not bound_var(Var).

% An exact equality may explicitly designate one leaf as its result.
#defined exact_assignment_mode/1.

exact_assignment_input_count(Mode,Count):-
    exact_assignment_mode(Mode),
    Count = #count {
        Arg : mode_variable_arg(Mode,Arg),
              not mode_arg_direction(Mode,Arg,output)
    }.

ready_exact_assignment(Slot):-
    selected(body,Slot,Mode),
    exact_assignment_mode(Mode),
    exact_assignment_input_count(Mode,Count),
    Count = #count {
        Arg,Var : mode_variable_arg(Mode,Arg),
                  not mode_arg_direction(Mode,Arg,output),
                  var_at(body,Slot,Arg,Var),
                  bound_var(Var)
    }.

bound_var(Var):-
    ready_exact_assignment(Slot),
    selected(body,Slot,Mode),
    mode_arg_direction(Mode,Arg,output),
    var_at(body,Slot,Arg,Var).

produced_var(Var):-
    ready_exact_assignment(Slot),
    selected(body,Slot,Mode),
    mode_arg_direction(Mode,Arg,output),
    var_at(body,Slot,Arg,Var).

safe_var(Var):-
    ready_exact_assignment(Slot),
    selected(body,Slot,Mode),
    mode_arg_direction(Mode,Arg,output),
    var_at(body,Slot,Arg,Var).

:- selected(body,Slot,Mode),
   exact_assignment_mode(Mode),
   not ready_exact_assignment(Slot).

:- selected(body,Slot,Mode), directed_mode(Mode), not ready_literal(Slot).

:- selected(head,Slot,Mode),
    not conditional_mode(Mode,_,_),
    mode_arg_direction(Mode,Arg,output),
    var_at(head,Slot,Arg,Var),
    not produced_var(Var).
