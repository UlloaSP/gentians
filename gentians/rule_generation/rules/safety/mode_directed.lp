% Optional input/output discipline for explicitly directed modes.

#defined mode_arg_direction/3.

directed_mode(Mode):- mode_arg_direction(Mode,_,input).
directed_mode(Mode):- mode_arg_direction(Mode,_,output).
input_count(Mode,Count):-
    directed_mode(Mode),
    Count = #count{Arg : mode_arg_direction(Mode,Arg,input)}.

bound_var(Var):-
    selected(head,Slot,Mode),
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

:- selected(body,Slot,Mode), directed_mode(Mode), not ready_literal(Slot).

:- selected(head,Slot,Mode),
    mode_arg_direction(Mode,Arg,output),
    var_at(head,Slot,Arg,Var),
    not produced_var(Var).
