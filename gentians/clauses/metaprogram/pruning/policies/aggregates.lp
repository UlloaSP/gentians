% Existing aggregate restrictions: distinct tuple and condition bindings,
% plus a result used outside the aggregate. These are restrictions of
% the enumerator; ASP itself also permits aggregates outside this subset.

:- aggregate_tuple_binding(Slot, First, Variable),
    aggregate_tuple_binding(Slot, Second, Variable), First < Second.

:- aggregate_condition_position(Slot, First, Variable),
    aggregate_condition_position(Slot, Second, Variable), First < Second.

:- aggregate_result_var(Slot, Variable), not var_used_outside_body_slot(Slot, Variable).

:- aggregate_output_var(Slot, Variable), not var_used_outside_body_slot(Slot, Variable).
