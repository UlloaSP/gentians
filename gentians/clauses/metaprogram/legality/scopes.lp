% Occurrences outside local constructs make a variable name clause-global.
% Separate aggregate/conditional interiors may reuse a name without binding one
% another. A local variable must be bound within its own element or conditional.
% Comparisons bind only when Clingo proves their output positions safe.

local_condition_bound(Section, Slot, conditional, -1, Var) :-
    conditional_positive_condition_var(Section, Slot, Condition, Var),
    selected(Section, Slot, Mode),
    not local_pool_missing_var(Section, Slot, Mode, conditional, -1, Condition, Var).

local_condition_bound(body, Slot, aggregate, Element, Var) :-
    aggregate_element_positive_condition_var(Slot, Element, Condition, Var),
    selected(body, Slot, Mode),
    not local_pool_missing_var(body, Slot, Mode, aggregate, Element, Condition, Var).

local_condition_bound(head, Slot, head_aggregate, 0, Var) :-
    head_aggregate_positive_condition_var(Slot, Condition, Var),
    selected(head, Slot, Mode),
    not local_pool_missing_var(head, Slot, Mode, head_aggregate, 0, Condition, Var).

local_pool_alternative_var(Section, Slot, Scope, Element, Condition, Alternative, Var) :-
    selected(Section, Slot, Mode),
    local_pool_alternative_arg(Mode, Scope, Element, Condition, Alternative, Position),
    var_at(Section, Slot, Position, Var).

local_pool_missing_var(Section, Slot, Mode, Scope, Element, Condition, Var) :-
    selected(Section, Slot, Mode),
    local_pool_condition_arg(Mode, Scope, Element, Condition, Position),
    var_at(Section, Slot, Position, Var),
    local_pool_alternative(Mode, Scope, Element, Condition, Alternative),
    not local_pool_alternative_var(Section, Slot, Scope, Element, Condition, Alternative, Var).

local_comparison_input_ready(Section, Slot, Scope, Element, Condition, Variant, Position) :-
    selected(Section, Slot, Mode),
    local_comparison_input(Mode, Scope, Element, Condition, Variant, Position),
    var_at(Section, Slot, Position, Var),
    local_condition_bound(Section, Slot, Scope, Element, Var).

local_comparison_input_ready(Section, Slot, Scope, Element, Condition, Variant, Position) :-
    selected(Section, Slot, Mode),
    local_comparison_input(Mode, Scope, Element, Condition, Variant, Position),
    var_at(Section, Slot, Position, Var),
    global_context_var(Var), asp_safe(Var).

local_condition_bound(Section, Slot, Scope, Element, Var) :-
    selected(Section, Slot, Mode),
    local_comparison_variant(Mode, Scope, Element, Condition, Variant, Required),
    Required <= #count { Input :
        local_comparison_input_ready(Section, Slot, Scope, Element, Condition, Variant, Input)
    },
    local_comparison_output(Mode, Scope, Element, Condition, Variant, Position),
    var_at(Section, Slot, Position, Var).

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

global_context_var(Var) :-
    selected(head, Slot, Mode), head_guard_arg(Mode, Arg),
    var_at(head, Slot, Arg, Var).

head_aggregate_element_position(head, Slot, Arg) :-
    selected(head, Slot, Mode), head_aggregate_element_arg(Mode, Arg).

head_aggregate_local_at(head, Slot, Arg) :-
    head_aggregate_element_position(head, Slot, Arg),
    var_at(head, Slot, Arg, Var), not global_context_var(Var).

local_var_at(head, Slot, Arg) :- head_aggregate_local_at(head, Slot, Arg).

head_aggregate_positive_condition_var(Slot, Condition, Var) :-
    selected(head, Slot, Mode),
    head_aggregate_positive_condition_arg(Mode, Condition, Arg),
    var_at(head, Slot, Arg, Var).

:- head_aggregate_local_at(head, Slot, Arg),
    var_at(head, Slot, Arg, Var),
    not local_condition_bound(head, Slot, head_aggregate, 0, Var).

conditional_local_var(Section, Slot, Var) :-
    conditional_var(Section, Slot, Var),
    not global_context_var(Var).

conditional_local_at(Section, Slot, Arg) :-
    selected(Section, Slot, Mode),
    conditional_local_var(Section, Slot, Var),
    var_at(Section, Slot, Arg, Var),
    conditional_mode(Mode),
    not head_guard_arg(Mode, Arg).

local_var_at(Section, Slot, Arg) :- conditional_local_at(Section, Slot, Arg).

:- conditional_local_var(Section, Slot, Var),
    not local_condition_bound(Section, Slot, conditional, -1, Var).

conditional_global_var(Section, Slot, Var) :-
    conditional_var(Section, Slot, Var),
    not conditional_local_var(Section, Slot, Var).

:- conditional_global_var(Section, Slot, Var), not asp_safe(Var).
