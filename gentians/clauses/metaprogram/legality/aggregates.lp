% Tuple variables are local and must occur in aggregate conditions.
% Global condition variables require positive normal body support, including
% when their names also occur as aggregate results. Result usage is checked
% outside their own slot under pruning/policies/aggregates.lp.

:- aggregate_tuple_var(Slot, Var), not aggregate_condition_var(Slot, Var).

:- aggregate_condition_var(Slot, Var),
    not aggregate_tuple_var(Slot, Var),
    global_context_var(Var),
    not normal_positive_body_var(Var).

:- aggregate_condition_var(_, Var), aggregate_result_var(_, Var), not normal_positive_body_var(Var).

:- aggregate_tuple_var(_, Var), global_context_var(Var).
