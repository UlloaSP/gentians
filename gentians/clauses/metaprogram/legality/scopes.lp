% Occurrences outside local constructs make a variable name clause-global.
% Separate aggregate/conditional interiors may reuse a name without binding one
% another. A conditional local must be bound by a positive condition, including
% in heads: its conclusion does not supply that binding.

local_var_at(body, Slot, Arg) :-
    aggregate_internal_arg(Slot, Arg),
    var_at(body, Slot, Arg, Var),
    not global_context_var(Var).

global_context_var(Var) :-
    selected(Section, Slot, Mode),
    not conditional_mode(Mode),
    var_at(Section, Slot, Arg, Var),
    not aggregate_internal_position(Section, Slot, Arg),
    not head_aggregate_element_position(Section, Slot, Arg).

head_aggregate_element_position(head, Slot, Arg) :-
    selected(head, Slot, Mode), head_aggregate_element_arg(Mode, Arg).

head_aggregate_local_at(head, Slot, Arg) :-
    head_aggregate_element_position(head, Slot, Arg),
    var_at(head, Slot, Arg, Var), not global_context_var(Var).

local_var_at(head, Slot, Arg) :- head_aggregate_local_at(head, Slot, Arg).

head_aggregate_positive_condition_var(Slot, Var) :-
    selected(head, Slot, Mode),
    head_aggregate_condition_arg(Mode, _, Arg),
    var_at(head, Slot, Arg, Var).

:- head_aggregate_local_at(head, Slot, Arg),
    var_at(head, Slot, Arg, Var),
    not head_aggregate_positive_condition_var(Slot, Var).

conditional_local_var(Section, Slot, Var) :-
    conditional_var(Section, Slot, Var),
    not global_context_var(Var).

conditional_local_at(Section, Slot, Arg) :-
    selected(Section, Slot, Mode),
    conditional_local_var(Section, Slot, Var),
    var_at(Section, Slot, Arg, Var),
    conditional_mode(Mode).

local_var_at(Section, Slot, Arg) :- conditional_local_at(Section, Slot, Arg).

:- conditional_local_var(Section, Slot, Var),
    not conditional_positive_condition_var(Section, Slot, Var).

conditional_global_var(Section, Slot, Var) :-
    conditional_var(Section, Slot, Var),
    not conditional_local_var(Section, Slot, Var).

:- conditional_global_var(Section, Slot, Var), not asp_safe(Var).
