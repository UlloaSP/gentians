% Reification of target(V0,V1) :- edge(V0,V1).
% Head: input/output. Body: input/output. Set source=2 for an unbound input.
#include "../../../gentians/clauses/metaprogram/legality/flow/declarations.lp".
#include "../../../gentians/clauses/metaprogram/legality/flow/seeds.lp".
#include "../../../gentians/clauses/metaprogram/legality/flow/closure.lp".
#include "../../../gentians/clauses/metaprogram/legality/flow/requirements.lp".

#defined conditional_mode/3.
#defined conditional_global_var/3.
#defined aggregate_result_var/2.
#defined arithmetic_mode/1.
#defined comparison_mode/1.
#defined mode_variable_arg/2.
#const source=0.

selected(head,0,0).
mode_arg_direction(0,0,input).
mode_arg_direction(0,1,output).
var_at(head,0,0,0).
var_at(head,0,1,1).

selected(body,0,1).
positive_mode(1).
mode_arg_direction(1,0,input).
mode_arg_direction(1,1,output).
var_at(body,0,0,source).
var_at(body,0,1,1).

#show ready_literal/1.
#show flow_bound/1.
#show flow_produced/1.
