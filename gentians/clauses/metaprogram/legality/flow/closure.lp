% Positive least fixed point of readiness and production. No body order is
% imposed. flow_produced implies flow_bound; any positions of positive normal
% atoms may bind without satisfying an output requirement.
%
% Mode readiness is not grounding safety. A relation output is also asp_safe
% only when its other arguments are asp_safe, never through a head input or
% through the output itself:
%   h(V0) :- V0=(V0*V0)+1.            rejected: V0 is only a head input
%   h(V0) :- d(V0), V1=(V0*V1)+1.     rejected: V1 would ground itself

ready_literal(Slot) :-
    selected(body, Slot, Mode),
    input_count(Mode, Count),
    Count <= #count{
        Arg, Var : mode_arg_direction(Mode, Arg, input),
                  var_at(body, Slot, Arg, Var),
                  flow_bound(Var)
    }.

flow_bound(Var) :-
    ready_literal(Slot),
    selected(body, Slot, Mode),
    binding_mode(Mode),
    mode_arg_direction(Mode, Arg, any),
    var_at(body, Slot, Arg, Var),
    not pooled_body_missing_var(Slot, Var).

flow_produced(Var) :-
    ready_literal(Slot),
    selected(body, Slot, Mode),
    binding_mode(Mode),
    mode_arg_direction(Mode, Arg, output),
    var_at(body, Slot, Arg, Var),
    not pooled_body_missing_var(Slot, Var).

ready_arithmetic(Slot) :-
    selected(body, Slot, Mode),
    arithmetic_mode(Mode),
    arithmetic_operand(Slot, left, Left),
    arithmetic_operand(Slot, right, Right),
    flow_bound(Left),
    flow_bound(Right).

flow_produced(Result) :-
    ready_arithmetic(Slot),
    arithmetic_result(Slot, Result).

ready_relation(Slot) :-
    selected(body, Slot, Mode),
    relation_output_mode(Mode),
    relation_input_count(Mode, Count),
    Count <= #count {
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

asp_ready_relation(Slot) :-
    selected(body, Slot, Mode),
    relation_output_mode(Mode),
    relation_input_count(Mode, Count),
    Count <= #count {
        Arg, Var : mode_variable_arg(Mode, Arg),
                  not mode_arg_direction(Mode, Arg, output),
                  var_at(body, Slot, Arg, Var),
                  asp_safe(Var)
    }.

asp_safe(Var) :-
    asp_ready_relation(Slot),
    selected(body, Slot, Mode),
    mode_arg_direction(Mode, Arg, output),
    var_at(body, Slot, Arg, Var).

flow_bound(Variable) :- flow_produced(Variable).
