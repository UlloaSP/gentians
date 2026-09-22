% Positive least fixed point of readiness and production. No body order is
% imposed. flow_produced implies flow_bound; any positions may bind without
% satisfying an output requirement. Clingo-proved relation outputs are also safe.

ready_literal(Slot) :-
    selected(body, Slot, Mode),
    input_count(Mode, Count),
    Count = #count{
        Arg, Var : mode_arg_direction(Mode, Arg, input),
                  var_at(body, Slot, Arg, Var),
                  flow_bound(Var)
    }.

flow_bound(Var) :-
    ready_literal(Slot),
    selected(body, Slot, Mode),
    positive_mode(Mode),
    mode_arg_direction(Mode, Arg, any),
    var_at(body, Slot, Arg, Var).

flow_produced(Var) :-
    ready_literal(Slot),
    selected(body, Slot, Mode),
    positive_mode(Mode),
    mode_arg_direction(Mode, Arg, output),
    var_at(body, Slot, Arg, Var).

ready_arithmetic(Slot) :-
    selected(body, Slot, Mode),
    arithmetic_mode(Mode),
    var_at(body, Slot, 0, Left),
    var_at(body, Slot, 1, Right),
    flow_bound(Left),
    flow_bound(Right).

flow_produced(Result) :-
    ready_arithmetic(Slot),
    var_at(body, Slot, 2, Result).

ready_relation(Slot) :-
    selected(body, Slot, Mode),
    relation_output_mode(Mode),
    relation_input_count(Mode, Count),
    Count = #count {
        Arg, Var : mode_variable_arg(Mode, Arg),
                  not mode_arg_direction(Mode, Arg, output),
                  var_at(body, Slot, Arg, Var),
                  flow_bound(Var)
    }.

flow_produced(Var) :-
    ready_relation(Slot),
    selected(body, Slot, Mode),
    mode_arg_direction(Mode, Arg, output),
    var_at(body, Slot, Arg, Var).

asp_safe(Var) :-
    ready_relation(Slot),
    selected(body, Slot, Mode),
    mode_arg_direction(Mode, Arg, output),
    var_at(body, Slot, Arg, Var).

flow_bound(Variable) :- flow_produced(Variable).
