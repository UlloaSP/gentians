pos(0..2).
num(0..1).
hd(0).
1{v0(Val,Pos) : num(Val)}1 :- pos(Pos).
1{v1(Val,Pos) : num(Val)}1 :- pos(Pos).
d(Pos,X):- v0(V0,Pos), v1(V1,Pos), X = |V0 - V1|.
