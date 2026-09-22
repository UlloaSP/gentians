% Occurrences outside local constructs make a variable name clause-global.
% Separate aggregate/conditional interiors may reuse a name without binding one
% another. A conditional local must be bound by a positive condition, including
% in heads: its conclusion does not supply that binding.

local_var_at(body,Slot,Arg):-
    aggregate_internal_arg(Slot,Arg),
    var_at(body,Slot,Arg,Var),
    not global_context_var(Var).

global_context_var(Var):-
    selected(Section,Slot,Mode),
    not conditional_mode(Mode,_,_),
    var_at(Section,Slot,Arg,Var),
    not aggregate_internal_position(Section,Slot,Arg).

conditional_local_var(body,Slot,Var):-
    conditional_var(body,Slot,Var),
    not global_context_var(Var).

conditional_local_var(head,Slot,Var):-
    conditional_var(head,Slot,Var),
    not global_context_var(Var).

conditional_local_at(Section,Slot,Arg):-
    selected(Section,Slot,Mode),
    conditional_local_var(Section,Slot,Var),
    var_at(Section,Slot,Arg,Var),
    conditional_mode(Mode,_,_).

local_var_at(Section,Slot,Arg):- conditional_local_at(Section,Slot,Arg).

:- conditional_local_var(Section,Slot,Var),
    not conditional_positive_condition_var(Section,Slot,Var).

conditional_global_var(Section,Slot,Var):-
    conditional_var(Section,Slot,Var),
    not conditional_local_var(Section,Slot,Var).

:- conditional_global_var(Section,Slot,Var), not safe_var(Var).
