possible_body(0, coin(V0)) :- var(V0, coin).
recall(0, 1).
constraint(0, positive).
at(coin(V0), 0, V0) :- possible_body(0, coin(V0)).
mapping(I, coin(V0), coin(M0)) :- var_assignment(I), possible_body(0, coin(V0)), var_assign(I, V0, M0).
possible_body(1, heads(V0)) :- var(V0, coin).
recall(1, 1).
at(heads(V0), 0, V0) :- possible_body(1, heads(V0)).
mapping(I, heads(V0), heads(M0)) :- var_assignment(I), possible_body(1, heads(V0)), var_assign(I, V0, M0).
possible_body(2, tails(V0)) :- var(V0, coin).
recall(2, 1).
at(tails(V0), 0, V0) :- possible_body(2, tails(V0)).
mapping(I, tails(V0), tails(M0)) :- var_assignment(I), possible_body(2, tails(V0)), var_assign(I, V0, M0).
possible_head(3, heads(V0)) :- var(V0, coin).
recall(3, 1).
at(heads(V0), 0, V0) :- possible_head(3, heads(V0)).
mapping(I, heads(V0), heads(M0)) :- var_assignment(I), possible_head(3, heads(V0)), var_assign(I, V0, M0).
possible_head(4, tails(V0)) :- var(V0, coin).
recall(4, 1).
at(tails(V0), 0, V0) :- possible_head(4, tails(V0)).
mapping(I, tails(V0), tails(M0)) :- var_assignment(I), possible_head(4, tails(V0)), var_assign(I, V0, M0).
var_type(coin).
maxv(3).
maxp(2).
max_body_literals(3).
max_rule_length(5).
max_wc_length(3).
maxhl(2).
minhl(1).

