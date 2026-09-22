% Compute input/output readiness to a fixed point, not textual literal order.
% Default negation produces no variables. Head inputs seed bound variables;
% a head output unified with a head input is supplied by that same input.
% Ordinary comparisons consume values; Clingo-proved relation outputs may bind
% new variables once their remaining leaves are bound.

#defined mode_arg_direction/3.
#defined relation_output_mode/1.

conditional_global_input_var(Var):-
    selected(Section,Slot,Mode),
    conditional_global_var(Section,Slot,Var),
    mode_arg_direction(Mode,Arg,input),
    var_at(Section,Slot,Arg,Var).

conditional_global_output_var(Var):-
    selected(Section,Slot,Mode),
    conditional_global_var(Section,Slot,Var),
    mode_arg_direction(Mode,Arg,output),
    var_at(Section,Slot,Arg,Var).

:- conditional_global_input_var(Var), not bound_var(Var).

:- conditional_global_output_var(Var), not produced_var(Var).

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

bound_var(Var):- aggregate_result_var(_,Var).

produced_var(Var):- aggregate_result_var(_,Var).

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

:- selected(body,Slot,Mode),
    comparison_mode(Mode),
    var_at(body,Slot,Arg,Var),
    not mode_arg_direction(Mode,Arg,output),
    not bound_var(Var).

relation_input_count(Mode,Count):-
    relation_output_mode(Mode),
    Count = #count {
        Arg : mode_variable_arg(Mode,Arg),
              not mode_arg_direction(Mode,Arg,output)
    }.

ready_relation(Slot):-
    selected(body,Slot,Mode),
    relation_output_mode(Mode),
    relation_input_count(Mode,Count),
    Count = #count {
        Arg,Var : mode_variable_arg(Mode,Arg),
                  not mode_arg_direction(Mode,Arg,output),
                  var_at(body,Slot,Arg,Var),
                  bound_var(Var)
    }.

bound_var(Var):-
    ready_relation(Slot),
    selected(body,Slot,Mode),
    mode_arg_direction(Mode,Arg,output),
    var_at(body,Slot,Arg,Var).

produced_var(Var):-
    ready_relation(Slot),
    selected(body,Slot,Mode),
    mode_arg_direction(Mode,Arg,output),
    var_at(body,Slot,Arg,Var).

safe_var(Var):-
    ready_relation(Slot),
    selected(body,Slot,Mode),
    mode_arg_direction(Mode,Arg,output),
    var_at(body,Slot,Arg,Var).

:- selected(body,Slot,Mode),
   relation_output_mode(Mode),
   not ready_relation(Slot).

:- selected(body,Slot,Mode), directed_mode(Mode), not ready_literal(Slot).

:- selected(head,Slot,Mode),
    not conditional_mode(Mode,_,_),
    mode_arg_direction(Mode,Arg,output),
    var_at(head,Slot,Arg,Var),
    not produced_var(Var).
