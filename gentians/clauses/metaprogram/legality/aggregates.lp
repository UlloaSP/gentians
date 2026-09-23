% Local variables need a positive atom or a Clingo-proved comparison binding
% in their own element.
% Clause-global occurrences need independent ASP-safe support. An aggregate
% result cannot make its own condition safe by circular assignment.

% The older single-condition equality-output subset retains its canonical
% local tuple projection and associated search-space restrictions.
:- aggregate_tuple_var(Slot, Var), not aggregate_condition_var(Slot, Var).

:- aggregate_condition_var(Slot, Var),
    not aggregate_tuple_var(Slot, Var),
    global_context_var(Var),
    not normal_positive_body_var(Var).

:- aggregate_condition_var(_, Var), aggregate_result_var(_, Var), not normal_positive_body_var(Var).

:- aggregate_tuple_var(_, Var), global_context_var(Var),
    not normal_positive_body_var(Var).

:- aggregate_element_arg(Slot, Element, Position),
    var_at(body, Slot, Position, Var),
    not global_context_var(Var),
    not local_condition_bound(body, Slot, aggregate, Element, Var).

:- aggregate_element_condition_var(Slot, Element, Var),
    not aggregate_element_tuple_var(Slot, Element, Var),
    global_context_var(Var), not normal_positive_body_var(Var).

:- aggregate_element_arg(Slot, Element, Position),
    var_at(body, Slot, Position, Var),
    global_context_var(Var), not asp_safe(Var).

:- aggregate_guard_var(_, Var), not asp_safe(Var).
