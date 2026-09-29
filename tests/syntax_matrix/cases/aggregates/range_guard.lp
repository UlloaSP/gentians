% Two guards around a multi-element #count.
% expect: ok :- 1<=#count{V0:p(V0);V0:q(V0)}<=2.
#maxv(1). #maxbl(1). #maxhl(1). #maxpl(1).
#modeh(1,ok).
#modeb(1,1<=#count{var(node,any):p(var(node,any));var(node,any):q(var(node,any))}<=2).
p(X) :- sp(X). q(X) :- sq(X).
sp(z) :- #false. sq(z) :- #false.
#pos({ok},{},{sp(a). sq(b).}).
#neg({ok},{},{sp(a). sp(b). sq(c).}).
#neg({ok},{},{}).
