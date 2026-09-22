% Reification of V0+V1=V2, where V0 and V1 have positive values.
% Set reverse=1 to require V2<V0, contradicting the inferred V0<V2.
#include "../../../gentians/clauses/metaprogram/representation/arithmetic.lp".
#include "../../../gentians/clauses/metaprogram/inference/numeric.lp".
#include "../../../gentians/clauses/metaprogram/pruning/contradictions/numeric.lp".

#defined mode/5.
#defined normal_mode/1.
#defined mode_arg_type/3.
#defined selected_leq/2.
#const reverse=0.

selected(body,0,0).
add_mode(0).
var_at(body,0,0,0).
var_at(body,0,1,1).
var_at(body,0,2,2).
positive_value(0).
positive_value(1).
selected_lt(2,0) :- reverse=1.

#show addition/4.
#show positive_value/1.
#show inferred_lt/2.
