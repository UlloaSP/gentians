% A #false conditional literal holds when no bad atom exists.
% expect: ok :- #false:bad(V0).
#maxv(1). #maxbl(2). #maxhl(1). #maxpl(1).
#modeh(1,ok).
#modeb(1,#false:bad(var(node,any))).
#modeb(1,bad(var(node,any))).
bad(X) :- flag(X).
flag(z) :- #false.
#pos({ok},{},{node(c).}).
#neg({ok},{},{flag(a).}).
