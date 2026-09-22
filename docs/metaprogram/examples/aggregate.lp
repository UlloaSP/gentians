% Reification of #count{V0,V1:edge(V0,V1)}=V2.
% Swapping condition bindings produces a rejected symmetric encoding.
#include "../../../gentians/clauses/metaprogram/representation/schema.lp".
#include "../../../gentians/clauses/metaprogram/representation/aggregates.lp".
#include "../../../gentians/clauses/metaprogram/symmetry/aggregates.lp".

#defined global_context_var/1.
#const swap=0.

selected(body,0,0).
mode_aggregate_tuple_arg(0,0,0).
mode_aggregate_tuple_arg(0,1,1).
mode_aggregate_condition_arg(0,0,0,2).
mode_aggregate_condition_arg(0,0,1,3).
mode_aggregate_result_arg(0,4).
aggregate_shape(0,2,1).
count_aggregate_mode(0).
aggregate_condition_atom(0,0,edge,2).
var_at(body,0,0,0).
var_at(body,0,1,1).
var_at(body,0,2,swap).
var_at(body,0,3,1-swap).
var_at(body,0,4,2).

#show aggregate_tuple_binding/3.
#show aggregate_condition_binding/4.
#show aggregate_result_var/2.
#show count_condition_orderable/1.
