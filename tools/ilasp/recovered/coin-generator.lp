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

%% General bias constraints.

cost(R, H) :- meta_rule_instance, head(H), possible_meta(ID, H), recall(ID, R).

1 { normal_rule ; disjunctive_rule : allow_disjunction ; choice_rule : not no_aggregates; constraint : not no_constraints; meta_rule_instance ; weak_constraint } 1.

1 { head(H) : possible_head(_, H) } 1 :- normal_rule.
2 { in_head(H) : possible_head(_, H); conditional_disjunct } :- disjunctive_rule.
:- conditional_disjunct, in_head(H), #false : condition(_, H).

MINHL { in_head(H) : possible_aggregate_head(_, H) } MAXHL :- choice_rule, minhl(MINHL), maxhl(MAXHL).

1 { ub(1..MAXHL) } 1 :- choice_rule, maxhl(MAXHL).
1 { lb(0..UB) } 1 :- choice_rule, ub(UB).

:- lb(LB), ub(UB), LB > UB.

{
  head(H) : possible_head(_, H), normal_rule;
  in_head(H) : possible_head(_, H), disjunctive_rule;
  in_head(H) : possible_aggregate_head(_, H), choice_rule;
  body(B) : possible_body(ID, B), not constraint(ID, negative);
  body(naf(B)) : possible_body(ID, B), not constraint(ID, positive);
  condition(C, B) : in_head(B), possible_conditional(ID, C), not constraint(ID, negative);
  condition(naf(C), B) : in_head(B), possible_conditional(ID, C), not constraint(ID, positive);
  condition(C, B) : body(B), possible_conditional(ID, C), not constraint(ID, negative);
  condition(naf(C), B) : body(B), possible_conditional(ID, C), not constraint(ID, positive)
} N :- max_rule_length(N), not weak_constraint, not meta_rule_instance.


{
  body(B) : possible_body(ID, B), not constraint(ID, negative);
  body(naf(B)) : possible_body(ID, B), not constraint(ID, positive);
  condition(C, B) : body(B), possible_conditional(ID, C), not constraint(ID, negative);
  condition(naf(C), B) : body(B), possible_conditional(ID, C), not constraint(ID, positive)
} N :- max_body_literals(N), not weak_constraint, not meta_rule_instance.

{
  body(B) : possible_body(ID, B), not constraint(ID, negative);
  body(naf(B)) : possible_body(ID, B), not constraint(ID, positive)
} R :- possible_body(ID, _), recall(ID, R), R > 0, not weak_constraint, not meta_rule_instance.

{
  condition(C, B) : possible_conditional(ID, C), not constraint(ID, negative);
  condition(naf(C), B) : possible_conditional(ID, C), not constraint(ID, positive)
} :- possible_conditional(ID, _), recall(ID, R), R > 0, body(B).

{
  weak_body(B) : possible_opt(ID, B), not constraint(ID, negative);
  weak_body(naf(B)) : possible_opt(ID, B), not constraint(ID, positive)
} R :- possible_opt(ID, _), recall(ID, R), R > 0, weak_constraint, not meta_rule_instance.

1 {
  weak_body(B) : possible_opt(ID, B), not constraint(ID, negative);
  weak_body(naf(B)) : possible_opt(ID, B), not constraint(ID, positive)
} N :- max_wc_length(N), weak_constraint, not meta_rule_instance.

variable(var__(1..N)) :- maxv(N).
{ var(V, T) : var_type(T), T != any } 1 :- variable(V).

:- variable(V1), variable(V2), V1 < V2,
   in_head(H1), at(H1, I2, V2),
   in_head(H2), at(H2, I2, V2),
   dmhv.

body(V, T) :- var(V, T), occurs_pos(V), strict_types.
body(V, T) :- var(V, T), occurs_non_pos(V), strict_types.
occurs_pos(V) :- occurs_non_pos(V), strict_types.

occurs_non_pos(V) :- body(V, T).
occurs_non_pos(V) :- variable(V), head(H), at(H, _, V); not condition(_, H).
occurs_pos(V) :- variable(V), body(H), at(H, _, V), #false: H = bin_exp(_, _, _); not condition(_, H).
occurs_pos(V) :- variable(V), weak_body(H), at(H, _, V), #false: H = bin_exp(_, _, _); not condition(_, H).
:- occurs_non_pos(V), not occurs_pos(V), not strict_types.
:- in_head(X), body(X).
:- head(X), body(X).
:- in_head(X), body(naf(X)).
:- head(X), body(naf(X)).
:- body(X), body(naf(X)).
:- weak_body(X), weak_body(naf(X)).

occurs_pos_conditional(L, V) :- variable(V), condition(B, L), at(B, _, V).

occurs_conditional(L, V) :- occurs_pos_conditional(L, V).
occurs_conditional(L, V) :- variable(V), condition(naf(B), L), at(B, _, V).
occurs_conditional(L, V) :- variable(V), condition(bin_exp(X, Y, Z), L), at(bin_exp(X, Y, Z), _, V).

:- occurs_conditional(L, V), occurs_conditional(L2, V), L < L2, not occurs_pos(V).
:- occurs_conditional(L, V), not occurs_pos(V), not occurs_conditional(_, V2), variable(V2), V2 < V.
:- body(X), condition(X, _), #false : condition(_, X).
:- condition(X, X).

:- condition(C, B), body(C).
:- condition(C, B), body(naf(C)).
:- condition(naf(C), B), body(C).

:- occurs_conditional(L, V), not occurs_pos_conditional(L, V), not occurs_pos(V).

occurs_non_pos(V) :- variable(V), in_head(H), at(H, _, V); not occurs_pos_conditional(H, V).
occurs_non_pos(V) :- variable(V), body(H), at(H, _, V); condition(_, H); not occurs_pos_conditional(H, V).
occurs_non_pos(V) :- variable(V), weak_body(H), at(H, _, V); condition(_, H); not occurs_pos_conditional(H, V).
occurs_non_pos(V) :- variable(V), body(naf(H)), at(H, _, V); not occurs_pos_conditional(naf(H), V).
occurs_non_pos(V) :- variable(V), weak_body(naf(H)), at(H, _, V); not occurs_pos_conditional(naf(H), V).
occurs_non_pos(V) :- variable(V), body(bin_exp(X, Y, Z)), at(bin_exp(X, Y, Z), _, V); not occurs_pos_conditional(bin_exp(X, Y, Z), V).
occurs_non_pos(V) :- variable(V), weak_body(bin_exp(X, Y, Z)), at(bin_exp(X, Y, Z), _, V); not occurs_pos_conditional(bin_exp(X, Y, Z), V).


negative(naf(B)) :- body(naf(B)).

in_any_body(B) :- body(B), not negative(B).
in_any_body(B) :- body(naf(B)).
in_any_body(B) :- weak_body(B), not negative(B).
in_any_body(B) :- weak_body(naf(B)).

:- occurs_pos(V), variable(V2), not occurs_pos(V2), V2 < V.


:- constraint, not body(_).

1 { priority(1..P) } 1 :- maxp(P), weak_constraint.
1 {
    weight(I) : integer_weight(I);
    weight(V) : type_weight(W), var(V, W), occurs_pos(V);
    weight(minus(V)) : type_weight(W), var(V, W), occurs_pos(V)
} 1 :- weak_constraint.

const(P, any, A) :- const(P, T, A).
const(P, T, A) :- meta_predicate(T, P, A).

1 { head(H) : possible_meta(_, H) } 1 :- meta_rule_instance.

anon(V) :- variable(V); 1 #count { BL, I : body(BL), at(BL, I, V); BL, I : body(naf(BL)), at(BL, I, V); BL, I : weak_body(BL), at(BL, I, V); BL, I : weak_body(naf(BL)), at(BL, I, V); BL, I : head(BL), at(BL, I, V); BL, I : in_head(BL), at(BL, I, V) } 1.

#show cost/2.
#show head/1.
#show in_head/1.
#show body/1.
#show body/2.
#show condition/2.
#show weak_body/1.
#show lb/1.
#show ub/1.
#show priority/1.
#show weight/1.
#show meta_rule_instance/0.
#show attribute/1.



%% Saturation encoding to avoid lots of extra equivalent rules

var_assignment(1).

var_assign(1, V1, V2) : variable(V2); var_assign(1, V1, Const) : const(Const, Type), var(V1, Type) :- variable(V1); not weak_constraint.
var_assign(1, V1, V2) :- variable(V1), variable(V2), saturate; not weak_constraint.
var_assign(1, V1, Const) :- variable(V1), const(Const, Type), var(V1, Type), saturate; not weak_constraint.

saturate :- body(B1), mapping(1, B1, B2), not body(B2); not weak_constraint.
saturate :- body(naf(B1)), mapping(1, B1, B2), not body(naf(B2)); not weak_constraint.

saturate :- mapping(1, B, B) : body(B), not negative(B); mapping(1, B, B) : body(naf(B)); not weak_constraint.

:- not saturate; not weak_constraint.

:- occurs_pos(V), variable(V2), V > V2, not occurs_pos(V2).

var_assignment(2).
var_assign(2, V1, V2) : occurs_pos(V2) :- occurs_pos(V1).
var_assign(2, V1, V2) :- occurs_pos(V1), occurs_pos(V2), saturate2.

internal(B) :- head(B), mapping(2, B, B2), head(B2).
internal(B) :- in_head(B), mapping(2, B, B2), in_head(B2).
internal(B) :- body(B), mapping(2, B, B2), body(B2).
internal(naf(B)) :- body(naf(B)), mapping(2, B, B2), body(naf(B2)).
internal(B) :- weak_body(B), mapping(2, B, B2), weak_body(B2).
internal(naf(B)) :- weak_body(naf(B)), mapping(2, B, B2), weak_body(naf(B2)).

saturate2 :-
  internal_head,
  internal_heads,
  internal_positive,
  internal_negative, not weak_constraint.

saturate2 :-
  internal_weak_positive,
  internal_weak_negative,
  weak_constraint.

internal_heads :- internal(L) : in_head(L), not condition(_, L); not weak_constraint.
internal_head :- internal(L) : head(L); not weak_constraint.
internal_positive :- internal(L) : body(L), not condition(_, L), not negative(L); not weak_constraint.
internal_negative :- internal(L) : body(L), not condition(_, L), negative(L); not weak_constraint.

internal_weak_positive :- internal(L) : weak_body(L), not condition(_, L), not negative(L); weak_constraint.
internal_weak_negative :- internal(L) : weak_body(L), not condition(_, L), negative(L); weak_constraint.

saturate2 :-
    in_head(H1), not condition(_, H1), mapping(2, H1, H2), not in_head(H2);
    internal(OH1) : in_head(OH1), OH1 > H2;
    not weak_constraint.

saturate2 :-
    internal_heads,
    head(H1), mapping(2, H1, H2);
    H1 < H2;
    not weak_constraint.

saturate2 :-
    internal_head,
    internal_heads,
    body(B1), not condition(_, B1), mapping(2, B1, B2), not body(B2);
    internal(OB1) : body(OB1), OB1 > B2, not negative(OB1);
    not weak_constraint.


saturate2 :-
    internal_head,
    internal_heads,
    internal_positive,
    body(naf(B1)), not condition(_, naf(B1)), mapping(2, B1, B2), not body(naf(B2));
    internal(OB1) : body(OB1), OB1 > B2, negative(OB1);
    not weak_constraint.

saturate2 :-
    weak_body(B1), not condition(_, B1), mapping(2, B1, B2), not weak_body(B2);
    internal(OB1) : weak_body(OB1), OB1 > B2, not negative(OB1);
    weak_constraint.


saturate2 :-
    internal_weak_positive,
    weak_body(naf(B1)), not condition(_, naf(B1)), mapping(2, B1, B2), not weak_body(naf(B2));
    internal(OB1) : weak_body(OB1), OB1 > B2, negative(OB1);
    weak_constraint.

saturate2 :- var_assign(2, X, Y), var_assign(2, Z, Y), X < Z.

:- not saturate2.



