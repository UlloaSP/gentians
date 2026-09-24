#const n = 12.
val(1..n).
partition(1..2).
1 { p(P, I) : partition(P) } 1 :- val(I).
p(1,1).
sq(Partition,Val):- p(Partition,V), Val = V*V.
