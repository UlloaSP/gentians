% Reification of #count{V0,V1:edge(V0,V1)}=V2.
% Swapping condition bindings produces a rejected symmetric encoding.
#include "../../../gentians/clauses/metaprogram/representation/aggregates.lp".
#include "../../../gentians/clauses/metaprogram/symmetry/aggregates.lp".

#defined global_context_var/1.
#const swap=0.

selected(body,0,0).
mode(body,0,0,5,1).
aggregate_mode(0,2,1).
count_aggregate_mode(0).
aggregate_condition_atom(0,0,edge,0,2).
var_at(body,0,0,0).
var_at(body,0,1,1).
var_at(body,0,2,swap).
var_at(body,0,3,1-swap).
var_at(body,0,4,2).

#show aggregate_tuple_binding/3.
#show aggregate_condition_binding/4.
#show aggregate_result_var/2.
#show count_condition_orderable/1.
