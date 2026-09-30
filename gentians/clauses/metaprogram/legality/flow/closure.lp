% Positive least fixed point of readiness and production. No body order is
% imposed. flow_produced implies flow_bound; any positions of positive normal
% atoms may bind without satisfying an output requirement.
%
% Mode readiness is not grounding safety. A relation output is also asp_safe
% only when its other arguments are asp_safe, never through a head input or
% through the output itself:
%   h(V0) :- V0=(V0*V0)+1.            rejected: V0 is only a head input
%   h(V0) :- d(V0), V1=(V0*V1)+1.     rejected: V1 would ground itself

% DEFINITION, reusable. ready_literal(Slot): the directed literal at body Slot
% has all its inputs available.
%   Slot  body slot of a directed mode in which every placeholder declared
%         input holds a flow_bound variable. A mode with no inputs is ready
%         at once.
% The count ranges over (position, variable) pairs, so an input name repeated
% at two input positions fills both. Shared by the two rules below and by
% legality/flow/requirements.lp, which rejects a directed literal that never
% becomes ready.
ready_literal(Slot) :-
    selected(body, Slot, Mode),
    input_count(Mode, Count),
    Count <= #count{
        Arg, Var : mode_arg_direction(Mode, Arg, input),
                  var_at(body, Slot, Arg, Var),
                  flow_bound(Var)
    }.

% DEFINITION, reusable. flow_bound(Var): Var has a value available to feed an
% input position.
%   Var  variable id.
% Weaker than flow_produced: it does not satisfy an output requirement.
% Defined here and in legality/flow/seeds.lp; consumed by the readiness rules
% of this file and by legality/flow/requirements.lp.
% Case: an "any" placeholder of a ready positive plain atom binds its
% variable, provided the atom grounds it in every binding alternative.
%   Slot  body slot of that ready atom.
%   Mode  its positive plain (binding) mode.
%   Arg   a placeholder of it declared any.
flow_bound(Var) :-
    ready_literal(Slot),
    selected(body, Slot, Mode),
    binding_mode(Mode),
    mode_arg_direction(Mode, Arg, any),
    var_at(body, Slot, Arg, Var),
    not pooled_body_missing_var(Slot, Var).

% DEFINITION, reusable. flow_produced(Var): some literal outputs Var.
%   Var  variable id.
% Only a produced variable satisfies a declared output. Defined here and in
% legality/flow/seeds.lp; consumed by the last rule of this file and by
% legality/flow/requirements.lp.
% Case 1: an output placeholder of a ready positive plain atom. With
% edge(input,output), "edge(V0,V1)" produces V1 once V0 is bound.
%   Slot  body slot of that ready atom.
%   Mode  its positive plain (binding) mode.
%   Arg   a placeholder of it declared output.
flow_produced(Var) :-
    ready_literal(Slot),
    selected(body, Slot, Mode),
    binding_mode(Mode),
    mode_arg_direction(Mode, Arg, output),
    var_at(body, Slot, Arg, Var),
    not pooled_body_missing_var(Slot, Var).

% DEFINITION, reusable. ready_arithmetic(Slot): the arithmetic literal at body
% Slot can be evaluated.
%   Slot  body slot of "Left op Right = Result" whose two operands are
%         flow_bound.
% Shared by the next rule and by legality/flow/requirements.lp.
ready_arithmetic(Slot) :-
    selected(body, Slot, Mode),
    arithmetic_mode(Mode),
    arithmetic_operand(Slot, left, Left),
    arithmetic_operand(Slot, right, Right),
    flow_bound(Left),
    flow_bound(Right).

% DEFINITION, reusable. flow_produced(Result), case 2: the result of a ready
% arithmetic literal.
%   Slot    body slot of that literal.
%   Result  variable id of its result.
flow_produced(Result) :-
    ready_arithmetic(Slot),
    arithmetic_result(Slot, Result).

% DEFINITION, reusable. ready_relation(Slot): the value-producing comparison
% at body Slot has all its non-output placeholders bound.
%   Slot  body slot of a relation_output_mode in which every variable
%         placeholder not declared output holds a flow_bound variable.
% Shared by the next rule and by legality/flow/requirements.lp.
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

% DEFINITION, reusable. flow_produced(Var), case 3: an output placeholder of
% a ready value-producing comparison.
%   Slot  body slot of that comparison.
%   Arg   a placeholder of it declared output.
flow_produced(Var) :-
    ready_relation(Slot),
    selected(body, Slot, Mode),
    mode_arg_direction(Mode, Arg, output),
    var_at(body, Slot, Arg, Var).

% DEFINITION, local helper. asp_ready_relation(Slot): the same readiness test
% as ready_relation, but counting asp_safe variables instead of flow_bound
% ones.
%   Slot  body slot of a value-producing comparison whose every non-output
%         placeholder holds an asp_safe variable.
% The two notions differ: a head input is flow_bound without being asp_safe.
% Used only by the next rule.
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

% DEFINITION, reusable. asp_safe(Var), the case missing from
% legality/asp_safety.lp: the output of a value-producing comparison whose
% other placeholders are all asp_safe.
%   Slot  body slot of that comparison.
%   Arg   a placeholder of it declared output.
%   Var   variable id written there; "d(V0), V1=V0+1" makes V1 safe.
asp_safe(Var) :-
    asp_ready_relation(Slot),
    selected(body, Slot, Mode),
    mode_arg_direction(Mode, Arg, output),
    var_at(body, Slot, Arg, Var).

% DEFINITION, reusable. flow_bound(Variable), closing case: whatever is
% produced is also bound, so it can feed the inputs of other literals.
flow_bound(Variable) :- flow_produced(Variable).
