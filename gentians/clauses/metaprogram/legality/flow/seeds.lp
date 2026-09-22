% Initial flow bindings: head inputs, aggregate results and undirected
% positive any positions. Head inputs satisfy a coincident head output.
% ASP grounding safety is checked separately in legality/asp_safety.lp.

flow_produced(Var) :-
    selected(head, Slot, Mode),
    not conditional_mode(Mode, _, _),
    mode_arg_direction(Mode, Arg, input),
    var_at(head, Slot, Arg, Var).

flow_bound(Var) :-
    selected(body, Slot, Mode),
    positive_mode(Mode),
    not directed_mode(Mode),
    mode_arg_direction(Mode, Arg, any),
    var_at(body, Slot, Arg, Var).

flow_produced(Var) :- aggregate_result_var(_, Var).
