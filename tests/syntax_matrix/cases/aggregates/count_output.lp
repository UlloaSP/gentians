% #count with an equality output bound into the head.
% expect: size(V1) :- #count{V0:p(V0)}=V1.
#maxv(2). #maxbl(1). #maxhl(1). #maxpl(1).
#modeh(1,size(var(numeric,input))).
#modeb(1,#count{var(node,any):p(var(node,any))}=var(numeric,output)).
#modeb(1,#count{var(node,any):q(var(node,any))}=var(numeric,output)).
p(a). p(b). q(c).
#pos({size(2)},{}).
#neg({size(1)},{}).
