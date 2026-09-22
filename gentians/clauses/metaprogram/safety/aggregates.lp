% Tuple variables are local and must occur in aggregate conditions.
% Global condition variables require positive normal body support, including
% when their names also occur as aggregate results. Results must be consumed
% outside their own slot so that the aggregate contributes to the clause.

:- aggregate_result_var(Slot,Var),
    not var_used_outside_body_slot(Slot,Var).

:- aggregate_tuple_var(Slot,Var), not aggregate_condition_var(Slot,Var).

:- aggregate_condition_var(Slot,Var),
    not aggregate_tuple_var(Slot,Var),
    global_context_var(Var),
    not normal_positive_body_var(Var).

:- aggregate_condition_var(_,Var), aggregate_result_var(_,Var), not normal_positive_body_var(Var).

:- aggregate_tuple_var(_,Var), global_context_var(Var).
