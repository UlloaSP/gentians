#const a=4.
#const b=2.
num(0..A) :- A = #max{a;b}.
zero(0).
pairprime(A,B) :- num(A), num(B), A > 1, B > 1, eucl(A,B,1).
result(M) :- eucl(a,b,M).
