% #modec comparison attached to a body conditional literal.
% expect: small_ok :- ok(V0):n(V0),V0<3.
#maxv(1). #maxbl(3). #maxhl(1). #maxpl(1).
#modeh(1,small_ok).
#modeb(1,ok(var(num,any))).
#modec(1,n(var(num,any))).
#modec(1,var(num,input)<3).
n(1..4).
ok(X) :- good(X).
good(0) :- #false.
#pos({small_ok},{},{good(1). good(2).}).
#neg({small_ok},{},{good(2). good(3). good(4).}).
