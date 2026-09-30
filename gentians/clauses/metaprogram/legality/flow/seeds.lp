% Initial flow bindings: head inputs, aggregate results and undirected
% positive any positions of normal body atoms. A head input is bound for body
% inputs and satisfies only a coincident head output (requirements.lp); it
% never produces a body output. Only a positive normal atom binds: comparison,
% arithmetic, aggregate and conditional positions never bind a global variable.
% ASP grounding safety is checked separately in legality/asp_safety.lp.

% DEFINITION, reusable. binding_mode(Mode): literals of this mode can supply
% variable values.
%   Mode  id of a plain atom template without default negation.
% Shared by the seed below and by legality/flow/closure.lp, so that "what may
% bind" is decided once.
binding_mode(Mode) :- normal_mode(Mode), positive_mode(Mode).

% DEFINITION, reusable. head_input_var(Var): the head receives Var as input.
%   Var  variable id at a placeholder declared input of a non-conditional head
%        literal. With target(input,output), "target(V0,V1)" gives V0.
% Shared by the seed below and by legality/flow/requirements.lp, where a head
% input also satisfies an output position of the head.
head_input_var(Var) :-
    selected(head, Slot, Mode),
    not conditional_mode(Mode),
    mode_arg_direction(Mode, Arg, input),
    var_at(head, Slot, Arg, Var).

% DEFINITION, reusable. flow_bound(Var), seed 1: every head input is bound
% from the start. See legality/flow/closure.lp for the meaning of flow_bound.
flow_bound(Var) :- head_input_var(Var).

% DEFINITION, reusable. flow_bound(Var), seed 2: an "any" placeholder of an
% undirected positive plain body atom binds its variable unconditionally.
%   Slot  body slot of that atom.
%   Mode  its mode: binding (positive plain atom) and not directed, so it has
%         no input to wait for.
%   Arg   a placeholder of it declared any.
%   Var   variable id written there, grounded in every binding alternative.
% With node(any), "node(V0)" binds V0. A directed atom binds its "any"
% positions only once ready (closure.lp).
flow_bound(Var) :-
    selected(body, Slot, Mode),
    binding_mode(Mode),
    not directed_mode(Mode),
    mode_arg_direction(Mode, Arg, any),
    var_at(body, Slot, Arg, Var),
    not pooled_body_missing_var(Slot, Var).

% DEFINITION, reusable. flow_produced(Var), seed 1: the equality output of any
% body aggregate is produced. See legality/flow/closure.lp for flow_produced.
flow_produced(Var) :- aggregate_output_var(_, Var).
% DEFINITION, reusable. flow_produced(Var), seed 2: the result of a
% single-element equality aggregate is produced.
flow_produced(Var) :- aggregate_result_var(_, Var).
