% Initial flow bindings: head inputs, aggregate results and undirected
% positive any positions of normal body atoms. A head input is bound for body
% inputs and satisfies only a coincident head output (requirements.lp); it
% never produces a body output. Only a positive normal atom binds: comparison,
% arithmetic, aggregate and conditional positions never bind a global variable.
% ASP grounding safety is checked separately in legality/asp_safety.lp.

binding_mode(Mode) :- normal_mode(Mode), positive_mode(Mode).

head_input_var(Var) :-
    selected(head, Slot, Mode),
    not conditional_mode(Mode),
    mode_arg_direction(Mode, Arg, input),
    var_at(head, Slot, Arg, Var).

flow_bound(Var) :- head_input_var(Var).

flow_bound(Var) :-
    selected(body, Slot, Mode),
    binding_mode(Mode),
    not directed_mode(Mode),
    mode_arg_direction(Mode, Arg, any),
    var_at(body, Slot, Arg, Var),
    not pooled_body_missing_var(Slot, Var).

flow_produced(Var) :- aggregate_output_var(_, Var).
flow_produced(Var) :- aggregate_result_var(_, Var).
