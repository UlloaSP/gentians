% exactly one variable per position
1{var_pos(Var,Pos) : var(Var)}1:- pos(Pos).

% only, safe variables (a variable in the head must appear in the body): TODO

% no variable should appear only once
at_least_twice(V):- var_pos(V,P0), var_pos(V,P1), P0 != P1.
:- var_pos(V,_), not at_least_twice(V).

% do not use variables of index k+1 if k is not used
:- var(Var0), var(Var1), Var0 < Var1, not var_pos(Var0,_), var_pos(Var1,_).

% fix variable 0 in position 0 to remove some symmetries
:- not var_pos(0,0).

