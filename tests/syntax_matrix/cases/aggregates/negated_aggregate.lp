% Default-negated aggregate literal.
% expect: ok :- not 1=#count{V0:p(V0)}.
#maxv(1). #maxbl(1). #maxhl(1). #maxpl(1).
#modeh(1,ok).
#modeb(1,not #count{var(node,any):p(var(node,any))}=1).
#modeb(1,#count{var(node,any):p(var(node,any))}=1).
p(X) :- sp(X).
sp(z) :- #false.
#pos({ok},{},{sp(a). sp(b).}).
#neg({ok},{},{sp(a).}).
