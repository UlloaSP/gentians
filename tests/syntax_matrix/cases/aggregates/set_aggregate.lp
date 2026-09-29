% Body set aggregate with negated condition.
% expect: ok :- 1<={p(V0):node(V0),not blocked(V0)}<=2.
#maxv(1). #maxbl(1). #maxhl(1). #maxpl(1).
#modeh(1,ok).
#modeb(1,1 {p(var(node,any)):node(var(node,any)),not blocked(var(node,any))} 2).
node(a). node(b). node(c).
p(X) :- sp(X). blocked(X) :- sb(X).
sp(z) :- #false. sb(z) :- #false.
#pos({ok},{},{sp(a).}).
#neg({ok},{},{sp(a). sb(a).}).
#neg({ok},{},{sp(a). sp(b). sp(c).}).
